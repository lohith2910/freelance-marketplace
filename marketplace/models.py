from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models


class Project(models.Model):
    client = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    budget = models.IntegerField(validators=[MinValueValidator(1)])
    milestone1 = models.BooleanField(default=False)
    milestone2 = models.BooleanField(default=False)
    milestone3 = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Application(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE)
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-applied_at"]

    def __str__(self):
        return f"{self.freelancer.username} applied for {self.project.title}"


class Bid(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.IntegerField(validators=[MinValueValidator(1)])
    proposal = models.TextField()
    delivery_days = models.IntegerField(validators=[MinValueValidator(1)])
    resume = models.FileField(upload_to="bid_resumes/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(default=False)
    plagiarism_percentage = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        import difflib
        other_bids = Bid.objects.exclude(id=self.id) if self.id else Bid.objects.all()
        max_ratio = 0.0
        if other_bids.exists() and self.proposal:
            proposal_clean = self.proposal.strip().lower()
            for other_bid in other_bids:
                if other_bid.proposal:
                    other_clean = other_bid.proposal.strip().lower()
                    ratio = difflib.SequenceMatcher(None, proposal_clean, other_clean).ratio()
                    if ratio > max_ratio:
                        max_ratio = ratio
        percentage = int(max_ratio * 100)
        self.plagiarism_percentage = percentage if percentage >= 40 else 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.freelancer.username} - Rs. {self.amount}"


class Profile(models.Model):
    ROLE_CHOICES = (
        ("client", "Client"),
        ("freelancer", "Freelancer"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    resume = models.FileField(upload_to="resumes/", blank=True, null=True)

    def __str__(self):
        return self.user.username


class Message(models.Model):
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.sender} -> {self.receiver}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message


class Payment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="payments")
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments_made")
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments_received")
    amount = models.IntegerField(validators=[MinValueValidator(1)])
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, default="Pending")  # Pending, Completed, Failed
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment of Rs. {self.amount} for {self.project.title} ({self.status})"

