from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.contrib.auth.models import User


class Course(models.Model):
    course_id = models.IntegerField(primary_key=True,
                                    validators=[MinValueValidator(0)])  # course id number as given by college
    name = models.CharField(max_length=100)  # course name as given by college
    mandatory = models.BooleanField()  # is the course mandatory (True) or an elective (False)
    credit_points = models.SmallIntegerField(
        validators=[MinValueValidator(1),
                    MaxValueValidator(20)])  # the credit points assigned to this course by the college
    syllabi = models.URLField(blank=True, null=True)  # link to syllabi of the course, not for use, currently
    avg_load = models.DecimalField(max_digits=6, decimal_places=5,
                                   validators=[MinValueValidator(1), MaxValueValidator(5)],
                                   blank=True, null=True)  # average course load, starts as null
    avg_rating = models.DecimalField(max_digits=6, decimal_places=5,
                                     validators=[MinValueValidator(1), MaxValueValidator(5)],
                                     blank=True, null=True)  # average course rating, starts as null
    num_of_raters = models.IntegerField(validators=[MinValueValidator(0)],
                                        default=0)  # number of raters for course rating and course load
    num_of_reviewers = models.IntegerField(validators=[MinValueValidator(0)],
                                           default=0)  # number of reviewers

    def __str__(self):
        return self.name

    def clean(self):
        rating = self.avg_rating
        load = self.avg_load
        raters = self.num_of_raters
        reviews = self.num_of_reviewers

        if (rating is not None) and (load is None):
            raise ValidationError("Can't have rating without load")
        if (rating is None) and (load is not None):
            raise ValidationError("Can't have load without rating")
        if ((rating is None) or (load is None)) and (raters > 0):
            raise ValidationError("Can't have raters that didn't rate")
        if ((rating is not None) or (load is not None)) and (raters == 0):
            raise ValidationError("Can't have ratings without raters")
        if ((raters == 0) or (load is None) or (rating is None)) and (reviews > 0):
            raise ValidationError("Can not have reviews without ratings")
        if (reviews > raters):
            raise ValidationError("Can not have reviews without ratings")

    def save(self, *args, **kwargs):
        try:
            self.clean()
        except ValidationError:
            return

        super().save(*args, **kwargs)

    # updates the course according to review output
    def update_course_per_review(self, reviewer_rating, reviewer_load, has_content):
        curr_raters = self.num_of_raters
        curr_reviewers = self.num_of_reviewers
        curr_avg_load = self.avg_load
        curr_avg_rating = self.avg_rating
        if curr_avg_load is None:
            self.avg_load = reviewer_load
            self.avg_rating = reviewer_rating
            self.num_of_raters = 1
        else:
            total_rating = curr_avg_rating * curr_raters
            total_rating += reviewer_rating
            total_load = curr_avg_load * curr_raters
            total_load += reviewer_load

            self.num_of_raters = curr_raters + 1
            self.avg_rating = total_rating / self.num_of_raters
            self.avg_load = total_load / self.num_of_raters

        if has_content:
            self.num_of_reviewers = curr_reviewers + 1

        self.save(update_fields=['avg_load', 'avg_rating', 'num_of_raters', 'num_of_reviewers'])

    def print_details(self):
        mandatory = 'yes' if self.mandatory else 'no'
        syllabi = 'Available' if self.syllabi else 'N/A'
        avg_rating = round(self.avg_rating, 3) if self.avg_rating else 'N/A'
        avg_load = round(self.avg_load, 3) if self.avg_load else 'N/A'
        msg = (
            "------------------------------------------------------------\n"
            f"Course indentifier: {self.course_id}   \nName: {self.name}\nMandatory? {mandatory}\n"
            f"Credit Points: {self.credit_points}\nSyllabi: {syllabi}\n"
            f"Average Rating: {avg_rating} \tAverage Load: {avg_load}\t"
            f"{self.num_of_raters} Raters\nNumber Of Reviews: {self.num_of_reviewers}"
            )
        print(msg)

    def get_details(self):
        return (self.course_id, self.name, self.mandatory, self.credit_points, self.syllabi,
                self.avg_load, self.avg_rating, self.num_of_raters, self.num_of_reviewers)

    # --- returns if course has Prerequisites
    def has_preqs(self):
        return Prerequisites.does_course_have_prerequisites(self)

    # --- returns all Course objects - the main 'courses' source for the view
    @staticmethod
    def get_courses():
        return Course.objects.all()

    # --- filters 'curr_courses' and returns the result according to 'filters'
    @staticmethod
    def get_filtered_courses(curr_courses, filters):
        active_filters = []
        for filter in filters:
            if(filter == 'mand'):
                curr_courses = Course.get_mandatory_courses(curr_courses)
                active_filters.append('mandatory')
            elif(filter == 'elect'):
                curr_courses = Course.get_elective_courses(curr_courses)
                active_filters.append('elective')
            elif(filter == 'load_below'):
                curr_courses = Course.get_filtered_courses_by_load(3.5, curr_courses)
                active_filters.append('course load under 3.5')
            elif(filter == 'rate_over'):
                curr_courses = Course.get_filtered_courses_by_rating(3.5, curr_courses)
                active_filters.append('course rating over 3.5')
            elif(filter == 'has_preqs'):
                curr_courses = Course.get_courses_with_preqs(curr_courses)
                active_filters.append('with prerequisites')
            elif(filter == 'no_preqs'):
                curr_courses = Course.get_courses_without_preqs(curr_courses)
                active_filters.append('without prerequisites')
            elif(filter == 'rater_num'):
                curr_courses = Course.get_courses_with_ratings(curr_courses, 5)
                active_filters.append('at least 5 raters')

        return {'result': curr_courses, 'active': active_filters}

    # --- sorts 'curr_courses' and return the result according to 'sort_val'
    @staticmethod
    def get_sorted_courses(curr_courses, sort_val):
        current_sorting = ''
        if(sort_val == 'name'):
            curr_courses = Course.sort_by_name(curr_courses)
            current_sorting = 'name'
        elif(sort_val == 'id'):
            curr_courses = Course.sort_by_id(curr_courses)
            current_sorting = 'identifier'
        elif(sort_val == 'rating'):
            curr_courses = Course.sort_by_rating(curr_courses)
            current_sorting = 'course rating'
        elif(sort_val == 'load'):
            curr_courses = Course.sort_by_load(curr_courses)
            current_sorting = 'course load'
        elif(sort_val == 'num_reviews'):
            curr_courses = Course.sort_by_num_reviews(curr_courses)
            current_sorting = 'number of reviews'
        elif(sort_val == 'num_raters'):
            curr_courses = Course.sort_by_num_raters(curr_courses)
            current_sorting = 'number of raters'

        return {'result': curr_courses, 'active': current_sorting}

    # --- all available filters:
    # get filtered course list by rating/load/mandatory/elective/prerequisites/num_of_Raters  - return QuerySets
    @staticmethod
    def get_filtered_courses_by_rating(rating, courses):
        # gets all courses with average rating >= rating
        return courses.filter(avg_rating__gte=rating)

    @staticmethod
    def get_filtered_courses_by_load(load, courses):
        # gets all courses with average course load <= load
        return courses.filter(avg_load__lte=load)

    @staticmethod
    def get_mandatory_courses(courses):
        # gets all courses that are mandatory
        return courses.filter(mandatory=True)

    @staticmethod
    def get_elective_courses(courses):
        # gets all courses that are electives
        return courses.filter(mandatory=False)

    @staticmethod
    def get_courses_with_preqs(courses):
        # gets all courses that have prerequisites
        have_preqs = Course.get_courses_with_preqs_ids(courses)
        return courses.filter(course_id__in=have_preqs)

    @staticmethod
    def get_courses_with_preqs_ids(courses):
        return [course.course_id for course in courses if course.has_preqs()]

    @staticmethod
    def get_courses_without_preqs(courses):
        # gets all courses that don't have prerequisites
        no_preqs = Course.get_courses_without_preqs_ids(courses)
        return courses.filter(course_id__in=no_preqs)

    @staticmethod
    def get_courses_without_preqs_ids(courses):
        return [course.course_id for course in courses if not course.has_preqs()]

    @staticmethod
    def get_courses_with_ratings(courses, num_of_ratings):
        return courses.filter(num_of_raters__gte=num_of_ratings)

    # --- all available sortings:
    @staticmethod
    def sort_by_name(courses):
        return courses.order_by('name')

    @staticmethod
    def sort_by_id(courses):
        return courses.order_by('course_id')

    @staticmethod
    def sort_by_rating(courses):
        return courses.order_by('-avg_rating')

    @staticmethod
    def sort_by_load(courses):
        return courses.order_by('avg_load')

    @staticmethod
    def sort_by_num_reviews(courses):
        return courses.order_by('-num_of_reviewers')

    @staticmethod
    def sort_by_num_raters(courses):
        return courses.order_by('-num_of_raters')

    # --- search methods:
    @staticmethod
    def get_courses_ordered_by_name(name):
        return Course.objects.filter(name__contains=name).order_by('name')


class Prerequisites(models.Model):
    # for   course A = the prerequisite course
    #       course B = the course the user wants to take
    # the relatiosnship between them, as depicted by req_code:
    #               -2  if there is no relation between taking course A before or during course B and taking course B
    #               -1  if  course B can't be taken if course A was taken (before or at the same time)
    # req_code =     0  if  course A must be taken at the same time (or before) course B
    #                1  if  course A must be taken before course B

    # choices for the req_code field
    class Req_Code(models.IntegerChoices):
        NONE = -2
        CANT = -1
        SIMU = 0
        BEFORE = 1

    # id of course B
    course_id = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='new_course_id', db_column='course_id')
    # id of course A
    req_course_id = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='required_course_id', db_column='req_course_id')
    # requirement code : depiction of the relationship between A and B as stated above
    req_code = models.SmallIntegerField(choices=Req_Code.choices, default=Req_Code.NONE)

    def __str__(self):
        return f'Req. Course = {self.req_course_id}, Desired Course = {self.course_id}, Req. Code = {self.req_code}'

    @staticmethod
    def get_prerequisites_for_course(course):
        return Prerequisites.objects.filter(course_id=course)

    @staticmethod
    def does_course_have_prerequisites(course):
        return Prerequisites.get_prerequisites_for_course(course).exists()


class AppUser(models.Model):
    # This field is the built-in django user model
    # We currently use the following attributes from the django user model: username, password, email, is_active
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)

    def __str__(self):
        return self.user.username

    def toggle_user_activation(self):
        self.user.is_active = not(self.user.is_active)

    @staticmethod
    # Creates a new app_user (without superuser permmisions) and saves it in the DB
    # The is_active attribute of AppUser.user is automaticly set to 'True' when creating a new AppUser
    def create_app_user(username, email, password):
        app_user = AppUser()
        app_user.user = User.objects.create_user(username, email, password)
        app_user.save()
        return app_user

    @staticmethod
    def get_all_app_users():
        return list(AppUser.objects.all())

    @staticmethod
    def get_app_user(username):
        try:
            user = User.objects.get(username=username)
            return AppUser.objects.get(user=user)
        except User.DoesNotExist:
            return None


class FollowedUserCourses(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    def __str__(self):
        return f'user = {self.user}, course = {self.course}'

    @staticmethod
    def get_courses_followed_by_app_user(app_user):
        pairs = FollowedUserCourses.objects.filter(user=app_user)
        # get only 'course' elements from user_course_pair elements
        return [user_course_pair.course for user_course_pair in pairs]


class Professor(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Professor_to_Course(models.Model):
    professor_id = models.ForeignKey(Professor, on_delete=models.CASCADE)
    course_id = models.ForeignKey(Course, on_delete=models.CASCADE)

    @staticmethod  # returns a list of Course objects
    def get_courses_by_professor(professor):
        pro_to_course_list = Professor_to_Course.objects.filter(professor_id=professor)
        return [arg.course_id for arg in pro_to_course_list]

    @staticmethod  # returns a list of Professor objects
    def get_professors_by_course(course):
        pro_to_course_list = Professor_to_Course.objects.filter(course_id=course)
        return [arg.professor_id for arg in pro_to_course_list]

    @staticmethod  # returns a queryset of Professor objects
    def get_queryset_professors_by_course(course):
        professor_list = Professor_to_Course.objects.filter(course_id=course).values('professor_id')
        return Professor.objects.filter(id__in=professor_list)

    def __str__(self):
        return f'professor = {self.professor_id.name}, course_id = {self.course_id.course_id}'


class Review(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE)
    rate = models.SmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    date = models.DateTimeField(default=timezone.now)
    content = models.TextField(null=True, blank=True)
    course_load = models.SmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    likes_num = models.SmallIntegerField(default=0)
    professor = models.ForeignKey(Professor, on_delete=models.CASCADE, null=True, blank=True)
    image = models.ImageField(null=True, blank=True, upload_to="images/")

    def __str__(self):
        MAX_WORDS_PREVIEW = 5
        MAX_LENGTH_PREVIEW = 40

        shortened_review = ' '.join(self.content.split()[:MAX_WORDS_PREVIEW])
        shortened_review = shortened_review[:MAX_LENGTH_PREVIEW]

        return f'Shortened review: {shortened_review}...'

    def print_details(self):
        message = (
            f"Course: {self.course}\n"
            f"User: {self.user}\n"
            f"Rating: {self.rate}\n"
            f"{str(self)}\n"    # shortened review content
            f"Course load: {self.course_load}\n"
            f"Likes number: {self.likes_num}\n"
            f"Professor: {self.professor if self.professor else 'N/A'}"
        )

        print(message)

    @classmethod
    def main_feed(cls):
        return cls.objects.order_by('-date')

    @classmethod
    def landing_page_feed(cls):
        return cls.objects.all().order_by('-date')[:3]

    @classmethod
    def profile_page_feed(cls, user):
        try:
            app_user = user.appuser
            return cls.objects.filter(user=app_user).order_by('-date')[:3]
        except ObjectDoesNotExist:
            return None

    @staticmethod
    def user_already_posted_review(user_id, course_id):
        return True if Review.objects.filter(user=user_id, course=course_id) else False

    def add_like(self):
        self.likes_num += 1
        self.save(update_fields=['likes_num'])

    def remove_like(self):
        self.likes_num -= 1
        self.save(update_fields=['likes_num'])


class UserLikes(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    review_id = models.ForeignKey(Review, on_delete=models.CASCADE)

    @staticmethod  # returns a list of Review objects
    def get_liked_reviews_by_user(user):
        user_likes_list = UserLikes.objects.filter(user_id=user)
        return [arg.review_id for arg in user_likes_list]

    @staticmethod  # returns a list of Review objects
    def get_liked_reviews_by_user_for_course(user, course):
        user_likes_list = UserLikes.objects.filter(user_id=user)
        return [arg.review_id for arg in user_likes_list if arg.review_id.course == course]

    @staticmethod  # returns a list of User objects
    def get_users_who_liked_review(review):
        user_likes_list = UserLikes.objects.filter(review_id=review)
        return [arg.user_id for arg in user_likes_list]

    @staticmethod
    def toggle_like(user, review):
        user_like = UserLikes.objects.filter(user_id=user, review_id=review)
        if user_like:
            user_like.delete()
            review.remove_like()
        else:
            user_like = UserLikes(user_id=user, review_id=review)
            user_like.save()
            review.add_like()
