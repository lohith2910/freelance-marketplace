from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum, Prefetch
from django.shortcuts import get_object_or_404, redirect, render

import razorpay

from .forms import AdminProjectForm, BidForm, ProfileForm, ProjectForm
from .models import Application, Bid, Message, Notification, Project, Payment


def get_user_role(user):
    if not user or user.is_anonymous:
        return None
    if user.is_staff:
        return "admin"
    return getattr(getattr(user, "profile", None), "role", None)


def role_required(*allowed_roles):
    def check(user):
        user_role = get_user_role(user)
        return user_role in allowed_roles or user_role == "admin"

    return user_passes_test(check, login_url="login")


def dashboard_url_for(user):
    role = get_user_role(user)
    if role == "admin":
        return "admin_dashboard"
    if role == "client":
        return "client_dashboard"
    if role == "freelancer":
        return "freelancer_dashboard"
    return "home"


def common_context(request):
    count = 0
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
    return {
        "notification_count": count,
        "user_role": get_user_role(request.user),
        "user": request.user,
    }


def render_page(request, template, context=None):
    data = common_context(request)
    data.update(context or {})
    return render(request, template, data)


def home(request):
    projects = Project.objects.select_related("client").filter(accepted=False)[:6]
    return render_page(request, "marketplace/home.html", {"projects": projects})


def projects(request):
    all_projects = Project.objects.select_related("client").filter(accepted=False)
    return render_page(request, "marketplace/projects.html", {"projects": all_projects})


def register_user(request):
    if request.user.is_authenticated:
        return redirect(dashboard_url_for(request.user))

    user_form = UserCreationForm(request.POST or None)
    profile_form = ProfileForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        user = user_form.save()
        profile = profile_form.save(commit=False)
        profile.user = user
        profile.save()
        messages.success(request, "Account created successfully. Please log in.")
        return redirect("login")

    return render_page(
        request,
        "marketplace/register.html",
        {"form": user_form, "profile_form": profile_form},
    )


def login_user(request):
    if request.user.is_authenticated:
        return redirect(dashboard_url_for(request.user))

    form = AuthenticationForm(request, data=request.POST or None)
    selected_role = request.POST.get("login_role", "client")

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if user is not None:
            user_role = get_user_role(user)
            login_role = request.POST.get("login_role")
            if login_role:
                if user.is_staff:
                    login(request, user)
                    return redirect(dashboard_url_for(user))
                elif login_role == "client" and user_role != "client":
                    form.add_error(None, "This account is not registered as a Client. Please select the Freelancer tab.")
                elif login_role == "freelancer" and user_role != "freelancer":
                    form.add_error(None, "This account is not registered as a Freelancer. Please select the Client tab.")
                else:
                    login(request, user)
                    return redirect(dashboard_url_for(user))
            else:
                login(request, user)
                return redirect(dashboard_url_for(user))

    return render_page(request, "marketplace/login.html", {"form": form, "selected_role": selected_role})


def logout_user(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")


@login_required(login_url="login")
def dashboard(request):
    return redirect(dashboard_url_for(request.user))


@login_required(login_url="login")
@role_required("client")
def add_project(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.client = request.user
        project.save()
        messages.success(request, "Project posted successfully.")
        return redirect("client_dashboard")

    return render_page(request, "marketplace/add_project.html", {"form": form})


@login_required(login_url="login")
@role_required("freelancer")
def quick_apply(request, project_id):
    project = get_object_or_404(Project, id=project_id, accepted=False)
    if project.client == request.user:
        messages.error(request, "You cannot apply to your own project.")
        return redirect("project_detail", pk=project.id)

    application, created = Application.objects.get_or_create(
        project=project,
        freelancer=request.user,
    )
    if created:
        Notification.objects.create(
            user=project.client,
            message=f"{request.user.username} applied to your project: {project.title}.",
        )
        messages.success(request, "Applied successfully.")
    else:
        messages.info(request, "You already applied to this project.")

    return redirect("freelancer_dashboard")


def project_detail(request, pk):
    project = get_object_or_404(Project.objects.select_related("client"), id=pk)
    has_applied = False
    has_bid = False
    bids = []
    if request.user.is_authenticated:
        has_applied = Application.objects.filter(project=project, freelancer=request.user).exists()
        has_bid = Bid.objects.filter(project=project, freelancer=request.user).exists()
        if project.client == request.user or request.user.is_staff:
            bids = Bid.objects.filter(project=project).select_related("freelancer").order_by("-created_at")
    return render_page(
        request,
        "marketplace/project_detail.html",
        {
            "project": project,
            "has_applied": has_applied,
            "has_bid": has_bid,
            "bids": bids,
        },
    )


@login_required(login_url="login")
@role_required("client")
def update_milestones(request, project_id):
    if request.user.is_staff:
        project = get_object_or_404(Project, id=project_id)
    else:
        project = get_object_or_404(Project, id=project_id, client=request.user)

    if request.method != "POST":
        return redirect("project_detail", pk=project.id)

    project.milestone1 = "milestone1" in request.POST
    project.milestone2 = "milestone2" in request.POST
    project.milestone3 = "milestone3" in request.POST
    project.save(update_fields=["milestone1", "milestone2", "milestone3"])

    messages.success(request, "Project milestones updated successfully.")
    return redirect("project_detail", pk=project.id)


@login_required(login_url="login")
@role_required("client")
def client_dashboard(request):
    client_projects = Project.objects.filter(client=request.user).prefetch_related(
        Prefetch("bid_set", queryset=Bid.objects.select_related("freelancer").order_by("-created_at"))
    ).annotate(
        application_count=Count("application", distinct=True),
        bid_count=Count("bid", distinct=True),
    )
    total_applications = Application.objects.filter(project__client=request.user).count()
    total_bids = Bid.objects.filter(project__client=request.user).count()
    in_progress = client_projects.filter(accepted=True).count()

    # Calculate payment stats
    payments_made = Payment.objects.filter(client=request.user, status="Completed")
    amount_paid = payments_made.aggregate(total=Sum("amount"))["total"] or 0

    # Count of accepted projects that have not been paid yet
    pending_payments = client_projects.filter(accepted=True, is_paid=False).count()

    # Fetch recent notifications for sidebar
    recent_notifications = Notification.objects.filter(user=request.user)[:5]

    return render_page(
        request,
        "marketplace/client_dashboard.html",
        {
            "projects": client_projects,
            "total_applications": total_applications,
            "total_bids": total_bids,
            "projects_in_progress": in_progress,
            "amount_paid": amount_paid,
            "pending_payments": pending_payments,
            "recent_notifications": recent_notifications,
        },
    )


@login_required(login_url="login")
@role_required("client")
def project_applications(request, project_id):
    if request.user.is_staff:
        project = get_object_or_404(Project, id=project_id)
    else:
        project = get_object_or_404(Project, id=project_id, client=request.user)
    applications = Application.objects.filter(project=project).select_related("freelancer")
    return render_page(
        request,
        "marketplace/project_applications.html",
        {"project": project, "applications": applications},
    )


@login_required(login_url="login")
@role_required("freelancer")
def place_bid(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if project.accepted:
        messages.info(request, "This project is already accepted and closed for new bids.")
        return redirect("project_detail", pk=project.id)

    if project.client == request.user:
        messages.error(request, "You cannot bid on your own project.")
        return redirect("project_detail", pk=project.id)

    existing_bid = Bid.objects.filter(project=project, freelancer=request.user).first()
    form = BidForm(request.POST or None, request.FILES or None, instance=existing_bid)

    if request.method == "POST" and form.is_valid():
        bid = form.save(commit=False)
        bid.project = project
        bid.freelancer = request.user
        if not bid.resume and hasattr(request.user, "profile") and request.user.profile.resume:
            bid.resume = request.user.profile.resume
        bid.save()
        Notification.objects.create(
            user=project.client,
            message=f"{request.user.username} placed a bid on your project: {project.title}.",
        )
        messages.success(request, "Bid saved successfully.")
        return redirect("freelancer_dashboard")

    return render_page(
        request,
        "marketplace/place_bid.html",
        {"project": project, "form": form, "existing_bid": existing_bid},
    )


@login_required(login_url="login")
@role_required("client")
def project_bids(request, project_id):
    if request.user.is_staff:
        project = get_object_or_404(Project, id=project_id)
    else:
        project = get_object_or_404(Project, id=project_id, client=request.user)
    bids = Bid.objects.filter(project=project).select_related("freelancer")
    return render_page(
        request,
        "marketplace/project_bids.html",
        {"project": project, "bids": bids},
    )


@login_required(login_url="login")
@role_required("client")
def accept_bid(request, bid_id):
    bid = get_object_or_404(Bid.objects.select_related("project", "freelancer"), id=bid_id)
    if bid.project.client != request.user and not request.user.is_staff:
        messages.error(request, "You can accept bids only for your own projects.")
        if request.user.is_staff:
            return redirect("admin_dashboard")
        return redirect("client_dashboard")

    Bid.objects.filter(project=bid.project).update(accepted=False)
    bid.accepted = True
    bid.save(update_fields=["accepted"])
    bid.project.accepted = True
    bid.project.save(update_fields=["accepted"])

    # Notify freelancer
    Notification.objects.create(
        user=bid.freelancer,
        message=f"Your bid for {bid.project.title} was accepted.",
    )
    # Notify client
    Notification.objects.create(
        user=request.user,
        message=f"You accepted {bid.freelancer.username}'s bid of Rs. {bid.amount} for: {bid.project.title}.",
    )
    messages.success(request, f"Bid from {bid.freelancer.username} accepted successfully.")
    
    referer = request.META.get("HTTP_REFERER")
    if referer:
        return redirect(referer)
    if request.user.is_staff:
        return redirect("admin_dashboard")
    return redirect("client_dashboard")


def auth_choice(request):
    return render_page(request, "marketplace/auth_choice.html")


@login_required(login_url="login")
@role_required("freelancer")
def freelancer_dashboard(request):
    applications = Application.objects.filter(freelancer=request.user).select_related("project")
    bids = Bid.objects.filter(freelancer=request.user).select_related("project", "project__client")
    accepted_bids = bids.filter(accepted=True)
    
    # Calculate earnings based on completed payments
    completed_payments = Payment.objects.filter(freelancer=request.user, status="Completed")
    total_earnings = completed_payments.aggregate(total=Sum("amount"))["total"] or 0
    
    # Calculate pending earnings (accepted bids not yet paid)
    all_accepted_amount = accepted_bids.aggregate(total=Sum("amount"))["total"] or 0
    pending_earnings = all_accepted_amount - total_earnings
    if pending_earnings < 0:
        pending_earnings = 0

    # Fetch recent notifications for sidebar
    recent_notifications = Notification.objects.filter(user=request.user)[:5]

    return render_page(
        request,
        "marketplace/freelancer_dashboard.html",
        {
            "applications": applications,
            "bids": bids,
            "accepted_bids": accepted_bids,
            "active_projects": accepted_bids.count(),
            "total_earnings": total_earnings,
            "pending_earnings": pending_earnings,
            "recent_notifications": recent_notifications,
        },
    )


@login_required(login_url="login")
def chat_view(request, project_id, receiver_id):
    project = get_object_or_404(Project, id=project_id)
    receiver = get_object_or_404(User, id=receiver_id)
    is_client = project.client == request.user
    is_project_freelancer = (
        Application.objects.filter(project=project, freelancer=request.user).exists()
        or Bid.objects.filter(project=project, freelancer=request.user).exists()
    )
    receiver_is_participant = receiver == project.client or Application.objects.filter(
        project=project,
        freelancer=receiver,
    ).exists() or Bid.objects.filter(project=project, freelancer=receiver).exists()

    if not (is_client or is_project_freelancer) or not receiver_is_participant:
        messages.error(request, "You do not have access to this chat.")
        return redirect(dashboard_url_for(request.user))

    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        if content:
            Message.objects.create(
                sender=request.user,
                receiver=receiver,
                project=project,
                content=content,
            )
            Notification.objects.create(
                user=receiver,
                message=f"New message from {request.user.username} regarding project: {project.title}."
            )
        return redirect("chat", project_id=project.id, receiver_id=receiver.id)

    chat_messages = Message.objects.filter(project=project).filter(
        Q(sender=request.user, receiver=receiver) | Q(sender=receiver, receiver=request.user)
    )
    return render_page(
        request,
        "marketplace/chat.html",
        {"project": project, "receiver": receiver, "messages": chat_messages},
    )


@login_required(login_url="login")
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user)
    notifications.filter(is_read=False).update(is_read=True)
    return render_page(
        request,
        "marketplace/notifications.html",
        {"notifications": notifications},
    )


@login_required(login_url="login")
def inbox(request):
    inbox_messages = Message.objects.filter(receiver=request.user).select_related(
        "sender",
        "project",
    )
    return render_page(request, "marketplace/inbox.html", {"messages": inbox_messages})


@login_required(login_url="login")
@role_required("client")
def payment_page(request, project_id):
    if request.user.is_staff:
        project = get_object_or_404(Project, id=project_id, accepted=True)
    else:
        project = get_object_or_404(Project, id=project_id, client=request.user, accepted=True)
    accepted_bid = Bid.objects.filter(project=project, accepted=True).first()
    if not accepted_bid:
        messages.error(request, "No accepted bid found for this project.")
        if request.user.is_staff:
            return redirect("admin_dashboard")
        return redirect("client_dashboard")
        
    freelancer = accepted_bid.freelancer
    amount = accepted_bid.amount

    # Create or update a pending Payment record
    payment_record, created = Payment.objects.get_or_create(
        project=project,
        client=project.client,
        freelancer=freelancer,
        amount=amount,
        status="Pending",
    )

    use_razorpay = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
    payment_order = None
    razorpay_key = settings.RAZORPAY_KEY_ID

    if use_razorpay:
        try:
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            payment_order = client.order.create(
                {
                    "amount": int(amount) * 100,
                    "currency": "INR",
                    "payment_capture": "1",
                }
            )
            # Update order ID on the record
            payment_record.razorpay_order_id = payment_order["id"]
            payment_record.save(update_fields=["razorpay_order_id"])
        except Exception:
            use_razorpay = False
            messages.info(
                request,
                "Unable to connect to Razorpay. Falling back to the Secure Mock Payment Simulator.",
            )

    if not use_razorpay:
        # Generate dummy payment ID for the UI
        import uuid
        payment_order = {
            "id": f"order_mock_{uuid.uuid4().hex[:12]}",
            "amount": int(amount) * 100,
        }
        payment_record.razorpay_order_id = payment_order["id"]
        payment_record.save(update_fields=["razorpay_order_id"])

    return render_page(
        request,
        "marketplace/payment.html",
        {
            "project": project,
            "payment": payment_order,
            "amount": amount,
            "razorpay_key": razorpay_key,
            "is_mock": not use_razorpay,
        },
    )


@csrf_exempt
@login_required(login_url="login")
@role_required("client")
def payment_callback(request, project_id):
    if request.user.is_staff:
        project = get_object_or_404(Project, id=project_id, accepted=True)
    else:
        project = get_object_or_404(Project, id=project_id, client=request.user, accepted=True)
    
    if request.method != "POST":
        if request.user.is_staff:
            return redirect("admin_dashboard")
        return redirect("client_dashboard")

    # Determine whether it's a real or mock payment
    is_mock = request.POST.get("is_mock") == "true"
    
    order_id = request.POST.get("razorpay_order_id")
    payment_id = request.POST.get("razorpay_payment_id")
    signature = request.POST.get("razorpay_signature")

    # Find the corresponding pending payment
    payment_record = Payment.objects.filter(
        project=project,
        client=project.client,
        status="Pending"
    ).first()

    if not payment_record:
        # Fallback to general lookup
        payment_record = Payment.objects.filter(project=project, client=project.client).first()

    if not payment_record:
        messages.error(request, "No transaction record found.")
        if request.user.is_staff:
            return redirect("admin_dashboard")
        return redirect("client_dashboard")

    if is_mock:
        # Simulated payment verification
        import uuid
        payment_record.razorpay_payment_id = payment_id or f"pay_mock_{uuid.uuid4().hex[:12]}"
        payment_record.status = "Completed"
        payment_record.save()
        
        project.is_paid = True
        project.save(update_fields=["is_paid"])

        # Create notifications
        Notification.objects.create(
            user=payment_record.freelancer,
            message=f"Payment of Rs. {payment_record.amount} received for project: {project.title}.",
        )
        Notification.objects.create(
            user=request.user,
            message=f"Payment of Rs. {payment_record.amount} successfully processed for project: {project.title}.",
        )

        messages.success(request, "Mock Payment of Rs. {} completed successfully!".format(payment_record.amount))
        return redirect("client_dashboard")
    else:
        # Verify Razorpay signature
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            messages.error(request, "Razorpay keys missing. Verification failed.")
            return redirect("client_dashboard")

        try:
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            # Verify signature
            client.utility.verify_payment_signature({
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature
            })
            
            payment_record.razorpay_payment_id = payment_id
            payment_record.razorpay_signature = signature
            payment_record.status = "Completed"
            payment_record.save()

            project.is_paid = True
            project.save(update_fields=["is_paid"])

            Notification.objects.create(
                user=payment_record.freelancer,
                message=f"Payment of Rs. {payment_record.amount} received for project: {project.title}.",
            )
            Notification.objects.create(
                user=request.user,
                message=f"Payment of Rs. {payment_record.amount} successfully processed for project: {project.title}.",
            )

            messages.success(request, "Payment of Rs. {} completed successfully via Razorpay!".format(payment_record.amount))
        except Exception as e:
            payment_record.status = "Failed"
            payment_record.save()
            messages.error(request, "Payment verification failed. Please try again.")

        return redirect("client_dashboard")


@login_required(login_url="login")
@role_required("admin")
def admin_dashboard(request):
    # Payment stats
    completed_payments = Payment.objects.filter(status="Completed")
    total_revenue = completed_payments.aggregate(total=Sum("amount"))["total"] or 0
    completed_payments_count = completed_payments.count()
    pending_payments_count = Payment.objects.filter(status="Pending").count()
    recent_payments = Payment.objects.select_related("project", "client", "freelancer")[:5]

    return render_page(
        request,
        "marketplace/admin_dashboard.html",
        {
            "total_users": User.objects.count(),
            "total_clients": User.objects.filter(profile__role="client").count(),
            "total_freelancers": User.objects.filter(profile__role="freelancer").count(),
            "total_projects": Project.objects.count(),
            "open_projects": Project.objects.filter(accepted=False).count(),
            "accepted_projects": Project.objects.filter(accepted=True).count(),
            "total_bids": Bid.objects.count(),
            "total_applications": Application.objects.count(),
            "recent_projects": Project.objects.select_related("client")[:5],
            "recent_bids": Bid.objects.select_related("project", "freelancer")[:5],
            "total_revenue": total_revenue,
            "completed_payments_count": completed_payments_count,
            "pending_payments_count": pending_payments_count,
            "recent_payments": recent_payments,
        },
    )


@login_required(login_url="login")
@role_required("admin")
def admin_users(request):
    role = request.GET.get("role")
    users = User.objects.select_related("profile").order_by("username")
    title = "All Users"

    if role in {"client", "freelancer"}:
        users = users.filter(profile__role=role)
        title = f"{role.title()}s"

    return render_page(
        request,
        "marketplace/admin_users.html",
        {"users": users, "title": title, "selected_role": role or "all"},
    )


@login_required(login_url="login")
@role_required("admin")
def admin_projects(request):
    status = request.GET.get("status")
    projects = Project.objects.select_related("client").annotate(
        application_count=Count("application"),
        bid_count=Count("bid"),
    )
    title = "All Projects"

    if status == "open":
        projects = projects.filter(accepted=False)
        title = "Open Projects"
    elif status == "accepted":
        projects = projects.filter(accepted=True)
        title = "Accepted Projects"

    return render_page(
        request,
        "marketplace/admin_projects.html",
        {"projects": projects, "title": title, "selected_status": status or "all"},
    )


@login_required(login_url="login")
@role_required("admin")
def admin_bids(request):
    bids = Bid.objects.select_related("project", "freelancer", "project__client")
    return render_page(request, "marketplace/admin_bids.html", {"bids": bids})


@login_required(login_url="login")
@role_required("admin")
def admin_applications(request):
    applications = Application.objects.select_related(
        "project",
        "freelancer",
        "project__client",
    )
    return render_page(
        request,
        "marketplace/admin_applications.html",
        {"applications": applications},
    )


@login_required(login_url="login")
@role_required("admin")
def admin_add_project(request):
    form = AdminProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Project added successfully for the selected client.")
        return redirect("admin_projects")

    return render_page(request, "marketplace/admin_add_project.html", {"form": form})


@login_required(login_url="login")
@role_required("admin")
def admin_payments(request):
    status_filter = request.GET.get("status", "all")
    payments = Payment.objects.select_related("project", "client", "freelancer")
    
    if status_filter in {"Pending", "Completed", "Failed"}:
        payments = payments.filter(status=status_filter)
        
    title = "All Payments"
    if status_filter != "all":
        title = f"{status_filter} Payments"

    return render_page(
        request,
        "marketplace/admin_payments.html",
        {
            "payments": payments,
            "title": title,
            "selected_status": status_filter,
        },
    )

