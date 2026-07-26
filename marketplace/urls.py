from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_user, name="login"),
    path("logout/", views.logout_user, name="logout"),
    path("register/", views.register_user, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("projects/", views.projects, name="projects"),
    path("project/<int:pk>/", views.project_detail, name="project_detail"),
    path(
        "project/<int:project_id>/milestones/",
        views.update_milestones,
        name="update_milestones",
    ),
    path("quick-apply/<int:project_id>/", views.quick_apply, name="quick_apply"),
    path("place-bid/<int:project_id>/", views.place_bid, name="place_bid"),
    path("client-dashboard/", views.client_dashboard, name="client_dashboard"),
    path("freelancer-dashboard/", views.freelancer_dashboard, name="freelancer_dashboard"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-dashboard/users/", views.admin_users, name="admin_users"),
    path("admin-dashboard/projects/", views.admin_projects, name="admin_projects"),
    path("admin-dashboard/bids/", views.admin_bids, name="admin_bids"),
    path(
        "admin-dashboard/applications/",
        views.admin_applications,
        name="admin_applications",
    ),
    path("admin-dashboard/add-project/", views.admin_add_project, name="admin_add_project"),
    path("add-project/", views.add_project, name="add_project"),
    path(
        "project/<int:project_id>/applications/",
        views.project_applications,
        name="project_applications",
    ),
    path("project/<int:project_id>/bids/", views.project_bids, name="project_bids"),
    path("accept-bid/<int:bid_id>/", views.accept_bid, name="accept_bid"),
    path("chat/<int:project_id>/<int:receiver_id>/", views.chat_view, name="chat"),
    path("notifications/", views.notifications_view, name="notifications"),
    path("inbox/", views.inbox, name="inbox"),
    path("payment/<int:project_id>/", views.payment_page, name="payment"),
    path("payment/<int:project_id>/callback/", views.payment_callback, name="payment_callback"),
    path("admin-dashboard/payments/", views.admin_payments, name="admin_payments"),
]
