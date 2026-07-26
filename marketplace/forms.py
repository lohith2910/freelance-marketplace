from django import forms
from django.contrib.auth.models import User

from .models import Bid, Profile, Project


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-control"
            if isinstance(field.widget, forms.Select):
                css_class = "form-select"
            field.widget.attrs.update({"class": css_class})


class ProjectForm(StyledModelForm):
    class Meta:
        model = Project
        fields = ["title", "description", "budget"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "budget": forms.NumberInput(attrs={"min": 1}),
        }


class AdminProjectForm(ProjectForm):
    client = forms.ModelChoiceField(
        queryset=User.objects.filter(profile__role="client").order_by("username"),
        empty_label="Select client",
    )

    class Meta(ProjectForm.Meta):
        fields = ["client", "title", "description", "budget"]


class ProfileForm(StyledModelForm):
    class Meta:
        model = Profile
        fields = ["role", "resume"]

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        resume = cleaned_data.get("resume")
        if role == "freelancer" and not resume:
            self.add_error("resume", "Resume is mandatory for Freelancers. Please upload your resume.")
        return cleaned_data

    def clean_resume(self):
        resume = self.cleaned_data.get("resume")
        if resume and not resume.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Please upload your resume as a PDF.")
        return resume


class BidForm(StyledModelForm):
    class Meta:
        model = Bid
        fields = ["amount", "proposal", "delivery_days", "resume"]
        widgets = {
            "amount": forms.NumberInput(attrs={"min": 1}),
            "delivery_days": forms.NumberInput(attrs={"min": 1}),
            "proposal": forms.Textarea(attrs={"rows": 5}),
        }

    def clean_resume(self):
        resume = self.cleaned_data.get("resume")
        if resume and not resume.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Please upload your resume as a PDF.")
        return resume

    def clean_proposal(self):
        proposal = self.cleaned_data.get("proposal")
        if not proposal:
            return proposal

        import difflib
        current_id = self.instance.id if self.instance else None
        other_bids = Bid.objects.exclude(id=current_id) if current_id else Bid.objects.all()

        max_ratio = 0.0
        proposal_clean = proposal.strip().lower()
        for other_bid in other_bids:
            if other_bid.proposal:
                other_clean = other_bid.proposal.strip().lower()
                ratio = difflib.SequenceMatcher(None, proposal_clean, other_clean).ratio()
                if ratio > max_ratio:
                    max_ratio = ratio

        plagiarism_percentage = int(max_ratio * 100)
        if plagiarism_percentage >= 40:
            raise forms.ValidationError(
                f"Plagiarism detected! Your proposal must have 0% plagiarism. "
                f"Similarity with another proposal is {plagiarism_percentage}%."
            )
        return proposal
