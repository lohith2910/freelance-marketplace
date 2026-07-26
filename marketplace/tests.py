from django.contrib.auth.models import User
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from .models import Application, Bid, Notification, Profile, Project


class MarketplaceWorkflowTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="client1",
            password="testpass123",
        )
        Profile.objects.create(user=self.client_user, role="client")

        self.freelancer = User.objects.create_user(
            username="freelancer1",
            password="testpass123",
        )
        Profile.objects.create(user=self.freelancer, role="freelancer")

        self.admin_user = User.objects.create_superuser(
            username="admin1",
            email="admin@example.com",
            password="testpass123",
        )

        self.project = Project.objects.create(
            client=self.client_user,
            title="Build Portfolio",
            description="Create a professional portfolio website.",
            budget=15000,
        )

    def test_login_redirects_user_by_role(self):
        response = self.client.post(
            reverse("login"),
            {"username": "client1", "password": "testpass123"},
        )
        self.assertRedirects(response, reverse("client_dashboard"))

        self.client.logout()
        response = self.client.post(
            reverse("login"),
            {"username": "freelancer1", "password": "testpass123"},
        )
        self.assertRedirects(response, reverse("freelancer_dashboard"))

        self.client.logout()
        response = self.client.post(
            reverse("login"),
            {"username": "admin1", "password": "testpass123"},
        )
        self.assertRedirects(response, reverse("admin_dashboard"))

    def test_admin_management_pages_render(self):
        self.client.force_login(self.admin_user)

        urls = [
            reverse("admin_dashboard"),
            reverse("admin_users"),
            f"{reverse('admin_users')}?role=client",
            reverse("admin_projects"),
            f"{reverse('admin_projects')}?status=open",
            reverse("admin_bids"),
            reverse("admin_applications"),
            reverse("admin_add_project"),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_admin_can_add_project_for_client(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("admin_add_project"),
            {
                "client": self.client_user.id,
                "title": "Admin Added Project",
                "description": "Created by admin for a client.",
                "budget": 30000,
            },
        )

        self.assertRedirects(response, reverse("admin_projects"))
        self.assertTrue(
            Project.objects.filter(
                client=self.client_user,
                title="Admin Added Project",
            ).exists()
        )

    def test_client_can_post_project(self):
        self.client.force_login(self.client_user)
        response = self.client.post(
            reverse("add_project"),
            {
                "title": "Django CRM",
                "description": "Build a CRM dashboard.",
                "budget": 25000,
            },
        )

        self.assertRedirects(response, reverse("client_dashboard"))
        self.assertTrue(Project.objects.filter(title="Django CRM", client=self.client_user).exists())

    def test_freelancer_cannot_open_client_dashboard(self):
        self.client.force_login(self.freelancer)
        response = self.client.get(reverse("client_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_freelancer_can_apply_once(self):
        self.client.force_login(self.freelancer)
        self.client.get(reverse("quick_apply", args=[self.project.id]))
        self.client.get(reverse("quick_apply", args=[self.project.id]))

        self.assertEqual(
            Application.objects.filter(project=self.project, freelancer=self.freelancer).count(),
            1,
        )
        self.assertEqual(Notification.objects.filter(user=self.client_user).count(), 1)

    def test_freelancer_can_bid_and_client_can_accept(self):
        self.client.force_login(self.freelancer)
        response = self.client.post(
            reverse("place_bid", args=[self.project.id]),
            {
                "amount": 12000,
                "proposal": "I can complete this with responsive design.",
                "delivery_days": 10,
            },
        )
        self.assertRedirects(response, reverse("freelancer_dashboard"))

        bid = Bid.objects.get(project=self.project, freelancer=self.freelancer)

        self.client.force_login(self.client_user)
        response = self.client.get(reverse("accept_bid", args=[bid.id]))
        self.assertRedirects(response, reverse("client_dashboard"))

        bid.refresh_from_db()
        self.project.refresh_from_db()
        self.assertTrue(bid.accepted)
        self.assertTrue(self.project.accepted)
        self.assertTrue(Notification.objects.filter(user=self.freelancer).exists())

    def test_other_client_cannot_view_project_bids(self):
        other_client = User.objects.create_user(username="client2", password="testpass123")
        Profile.objects.create(user=other_client, role="client")
        self.client.force_login(other_client)

        response = self.client.get(reverse("project_bids", args=[self.project.id]))
        self.assertEqual(response.status_code, 404)

    def test_closed_project_bid_redirects_to_detail(self):
        self.project.accepted = True
        self.project.save(update_fields=["accepted"])
        self.client.force_login(self.freelancer)

        response = self.client.get(reverse("place_bid", args=[self.project.id]))

        self.assertRedirects(response, reverse("project_detail", args=[self.project.id]))

    def test_client_can_update_project_milestones(self):
        self.client.force_login(self.client_user)

        response = self.client.post(
            reverse("update_milestones", args=[self.project.id]),
            {"milestone1": "on", "milestone3": "on"},
        )

        self.assertRedirects(response, reverse("project_detail", args=[self.project.id]))
        self.project.refresh_from_db()
        self.assertTrue(self.project.milestone1)
        self.assertFalse(self.project.milestone2)
        self.assertTrue(self.project.milestone3)

    def test_freelancer_cannot_update_project_milestones(self):
        self.client.force_login(self.freelancer)

        response = self.client.post(
            reverse("update_milestones", args=[self.project.id]),
            {"milestone1": "on"},
        )

        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertFalse(self.project.milestone1)

    def test_other_client_cannot_update_project_milestones(self):
        other_client = User.objects.create_user(username="client3", password="testpass123")
        Profile.objects.create(user=other_client, role="client")
        self.client.force_login(other_client)

        response = self.client.post(
            reverse("update_milestones", args=[self.project.id]),
            {"milestone1": "on"},
        )

        self.assertEqual(response.status_code, 404)
        self.project.refresh_from_db()
        self.assertFalse(self.project.milestone1)

    @override_settings(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="")
    def test_payment_without_gateway_keys_redirects(self):
        self.project.accepted = True
        self.project.save(update_fields=["accepted"])
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("payment", args=[self.project.id]))

        self.assertRedirects(response, reverse("client_dashboard"))

    def test_freelancer_registration_requires_resume(self):
        data = {
            "username": "newfreelancer",
            "password1": "somepassword123",
            "password2": "somepassword123",
            "role": "freelancer",
        }
        response = self.client.post(reverse("register"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resume is mandatory for Freelancers")

    def test_client_registration_does_not_require_resume(self):
        data = {
            "username": "newclient",
            "password1": "somepassword123",
            "password2": "somepassword123",
            "role": "client",
        }
        response = self.client.post(reverse("register"), data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("login"))

    def test_login_role_mismatch_fails(self):
        response = self.client.post(
            reverse("login"),
            {"username": "client1", "password": "testpass123", "login_role": "freelancer"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This account is not registered as a Freelancer")

    def test_notifications_marked_read_on_view(self):
        notification = Notification.objects.create(
            user=self.client_user,
            message="Test notification message.",
        )
        self.assertFalse(notification.is_read)

        self.client.force_login(self.client_user)
        response = self.client.get(reverse("notifications"))
        self.assertEqual(response.status_code, 200)

        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_bid_resume_falls_back_to_profile_resume(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        pdf_content = b"%PDF-1.4 ... dummy pdf content"
        resume_file = SimpleUploadedFile("my_resume.pdf", pdf_content, content_type="application/pdf")

        profile = self.freelancer.profile
        profile.resume = resume_file
        profile.save()

        self.client.force_login(self.freelancer)
        response = self.client.post(
            reverse("place_bid", args=[self.project.id]),
            {
                "amount": 10000,
                "proposal": "I will do the work.",
                "delivery_days": 5,
            }
        )
        self.assertRedirects(response, reverse("freelancer_dashboard"))

        bid = Bid.objects.get(project=self.project, freelancer=self.freelancer)
        self.assertTrue(bid.resume)
        self.assertEqual(bid.resume.name, profile.resume.name)

    def test_client_can_view_bids_on_project_details_and_accept_bid(self):
        bid = Bid.objects.create(
            project=self.project,
            freelancer=self.freelancer,
            amount=13500,
            proposal="I will build the project detail acceptance feature.",
            delivery_days=3,
        )

        self.client.force_login(self.client_user)
        project_detail_url = reverse("project_detail", args=[self.project.id])
        response = self.client.get(project_detail_url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Bids Received")
        self.assertContains(response, "freelancer1")
        self.assertContains(response, "Rs. 13500")
        self.assertContains(response, "I will build the project detail acceptance feature.")

        accept_url = reverse("accept_bid", args=[bid.id])
        response = self.client.get(accept_url, HTTP_REFERER=project_detail_url)

        self.assertRedirects(response, project_detail_url)

        bid.refresh_from_db()
        self.project.refresh_from_db()
        self.assertTrue(bid.accepted)
        self.assertTrue(self.project.accepted)

        response = self.client.get(project_detail_url)
        self.assertContains(response, "Accepted Bid")
        self.assertNotContains(response, "Accept Bid")

    def test_admin_can_view_bids_on_project_details_and_accept_bid(self):
        bid = Bid.objects.create(
            project=self.project,
            freelancer=self.freelancer,
            amount=14000,
            proposal="Admin acceptance test.",
            delivery_days=4,
        )

        self.client.force_login(self.admin_user)
        project_detail_url = reverse("project_detail", args=[self.project.id])
        response = self.client.get(project_detail_url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Bids Received")
        self.assertContains(response, "freelancer1")
        self.assertContains(response, "Rs. 14000")
        self.assertContains(response, "Admin acceptance test.")

        accept_url = reverse("accept_bid", args=[bid.id])
        response = self.client.get(accept_url, HTTP_REFERER=project_detail_url)

        self.assertRedirects(response, project_detail_url)

        bid.refresh_from_db()
        self.project.refresh_from_db()
        self.assertTrue(bid.accepted)
        self.assertTrue(self.project.accepted)

    def test_admin_can_view_project_bids_and_applications_pages(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("project_bids", args=[self.project.id]))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("project_applications", args=[self.project.id]))
        self.assertEqual(response.status_code, 200)

    def test_plagiarism_enforcement_prevents_duplicate_proposal(self):
        Bid.objects.create(
            project=self.project,
            freelancer=self.freelancer,
            amount=10000,
            proposal="This is a very unique and creative proposal for building this portfolio.",
            delivery_days=5,
        )

        other_freelancer = User.objects.create_user(
            username="freelancer2",
            password="testpass123",
        )
        Profile.objects.create(user=other_freelancer, role="freelancer")
        self.client.force_login(other_freelancer)

        response = self.client.post(
            reverse("place_bid", args=[self.project.id]),
            {
                "amount": 9000,
                "proposal": "This is a very unique and creative proposal for building this portfolio.",
                "delivery_days": 4,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Plagiarism detected! Your proposal must have 0% plagiarism. Similarity with another proposal is 100%."
        )

    def test_unique_proposal_accepted(self):
        Bid.objects.create(
            project=self.project,
            freelancer=self.freelancer,
            amount=10000,
            proposal="This is a very unique and creative proposal for building this portfolio.",
            delivery_days=5,
        )

        other_freelancer = User.objects.create_user(
            username="freelancer3",
            password="testpass123",
        )
        Profile.objects.create(user=other_freelancer, role="freelancer")
        self.client.force_login(other_freelancer)

        response = self.client.post(
            reverse("place_bid", args=[self.project.id]),
            {
                "amount": 9500,
                "proposal": "An entirely fresh approach to completing your website using modern layout and CSS grid.",
                "delivery_days": 6,
            },
        )
        self.assertRedirects(response, reverse("freelancer_dashboard"))
        new_bid = Bid.objects.get(freelancer=other_freelancer)
        self.assertEqual(new_bid.plagiarism_percentage, 0)
