from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from .forms import ProfileForm


class ManualMascotTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mascot-user", password=None)
        self.client.force_login(self.user)

    def test_measurements_do_not_change_any_selected_mascot(self):
        profile = self.user.profile
        for selection in ("ACTIVE", "BALANCED", "SOFT", "MUSCULAR", "AUTO", "SLIM"):
            profile.avatar_preference = selection
            before = profile.body_style
            for height, weight, muscle, gender, age in ((180, 50, 10, "M", 10), (150, 110, 70, "F", 80)):
                profile.height_cm, profile.weight_kg = height, weight
                profile.skeletal_muscle_kg, profile.gender, profile.age = muscle, gender, age
                self.assertEqual(profile.body_style, before)
                self.assertIsNotNone(profile.bmi)

    def test_four_choices_and_legacy_default(self):
        form = ProfileForm(instance=self.user.profile, user=self.user)
        self.assertEqual(list(form.fields["avatar_preference"].choices), [
            ("ACTIVE", "백호"), ("MUSCULAR", "포동"), ("SOFT", "토리"), ("BALANCED", "아콩")])
        self.assertEqual(form.initial["avatar_preference"], "ACTIVE")

    def test_selection_persists_alongside_measurement_history(self):
        data = dict(nickname="mascot-user", area="서울특별시", gender="F", age=65,
                    height_cm=170, weight_kg=90, skeletal_muscle_kg=50,
                    measured_on="2026-09-15", avatar_preference="SOFT")
        self.assertRedirects(self.client.post(reverse("profile"), data), reverse("profile"))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.character_label, "토리")
        self.assertEqual(self.user.body_measurements.count(), 1)
        data.update(weight_kg=50, skeletal_muscle_kg=15, gender="M", age=20)
        self.assertRedirects(self.client.post(reverse("profile"), data), reverse("profile"))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.character_label, "토리")
        self.assertEqual(self.user.body_measurements.count(), 2)
        self.assertContains(self.client.get(reverse("dashboard")), "style-soft")
