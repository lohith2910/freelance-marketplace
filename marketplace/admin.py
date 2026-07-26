from django.contrib import admin

from .models import Application, Bid, Message, Notification, Profile, Project, Payment



@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "budget", "accepted", "created_at")
    list_filter = ("accepted", "created_at")
    search_fields = ("title", "description", "client__username")


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("project", "freelancer", "amount", "delivery_days", "accepted")
    list_filter = ("accepted", "created_at")
    search_fields = ("project__title", "freelancer__username", "proposal")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("project", "freelancer", "applied_at")
    search_fields = ("project__title", "freelancer__username")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "resume")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "created_at")
    search_fields = ("user__username", "message")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "project", "timestamp")
    search_fields = ("sender__username", "receiver__username", "project__title", "content")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("project", "client", "freelancer", "amount", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("project__title", "client__username", "freelancer__username", "razorpay_order_id", "razorpay_payment_id")

