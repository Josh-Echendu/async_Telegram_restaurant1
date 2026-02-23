from rest_framework.pagination import LimitOffsetPagination 


class CustomLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 3
    max_limit = 5  # prevents the bot from trying to send 50 images at once
