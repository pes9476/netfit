from datetime import date
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import CardBattle, Profile, WorkoutRecord, needs_kakao_nickname

class RegisterForm(UserCreationForm):
    area = forms.ChoiceField(choices=Profile._meta.get_field("area").choices)

    class Meta:
        model = User
        fields = ("username", "area", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit)
        user.profile.area = self.cleaned_data["area"]
        user.profile.save()
        return user

class WorkoutForm(forms.ModelForm):
    class Meta:
        model = WorkoutRecord
        fields = ("workout_type", "custom_workout_name", "minutes", "distance_km", "location", "proof_image")
        widgets = {
            "workout_type": forms.Select(attrs={"class": "input"}),
            "custom_workout_name": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "예: 필라테스, 농구, 등산",
                "maxlength": 50,
            }),
            "minutes": forms.NumberInput(attrs={"class": "input", "min": 1, "placeholder": "예: 30"}),
            "distance_km": forms.NumberInput(attrs={"class": "input", "min": 0, "step": "0.1", "placeholder": "예: 3.5"}),
            "location": forms.TextInput(attrs={"class": "input", "placeholder": "예: OO 체육공원 (미입력 가능)"}),
            "proof_image": forms.FileInput(attrs={"class": "input", "accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["workout_type"].choices = [
            ("러닝", "러닝"),
            ("걷기", "산책"),
            ("수영", "수영"),
            ("배드민턴", "배드민턴"),
            ("자전거", "자전거"),
            ("헬스", "헬스"),
            ("등산", "등산"),
            ("축구", "축구"),
            ("농구", "농구"),
            ("요가", "요가"),
            ("기타", "직접입력"),
        ]
        self.fields["workout_type"].label = "운동 종류"
        self.fields["custom_workout_name"].label = "직접 입력할 운동"
        self.fields["custom_workout_name"].required = False
        self.fields["minutes"].label = "운동 시간 (분)"
        self.fields["distance_km"].label = "거리 (km)"
        self.fields["distance_km"].required = False
        self.fields["location"].label = "운동 장소 (선택)"
        self.fields["location"].required = False
        self.fields["proof_image"].label = "인증 사진 추가 (선택)"
        self.fields["proof_image"].required = False

    def clean(self):
        cleaned_data = super().clean()
        workout_type = cleaned_data.get("workout_type")
        custom_name = (cleaned_data.get("custom_workout_name") or "").strip()
        if workout_type == "기타" and not custom_name:
            self.add_error("custom_workout_name", "직접 입력할 운동 이름을 적어주세요.")
        elif workout_type != "기타":
            cleaned_data["custom_workout_name"] = ""
        else:
            cleaned_data["custom_workout_name"] = custom_name
        return cleaned_data

class BattleForm(forms.ModelForm):
    class Meta:
        model = CardBattle
        fields = ("scope", "opponent_name", "region_name", "reward", "custom_reward")
        widgets = {
            "scope": forms.Select(attrs={"class": "input"}),
            "opponent_name": forms.TextInput(attrs={"class": "input", "placeholder": "예: 민수 또는 강서구 러너 팀"}),
            "region_name": forms.TextInput(attrs={"class": "input", "placeholder": "지역 배틀일 때 입력"}),
            "reward": forms.Select(attrs={"class": "input", "id": "rewardSelect"}),
            "custom_reward": forms.TextInput(attrs={"class": "input", "id": "customReward", "placeholder": "직접 정한 보상 입력"}),
        }

class ProfileForm(forms.ModelForm):
    avatar_preference = forms.ChoiceField(
        label="마스코트 선택",
        choices=[("ACTIVE", "백호"), ("MUSCULAR", "백곰"),
                 ("SOFT", "햄스터"), ("BALANCED", "아기공룡")],
        widget=forms.Select(attrs={"class": "input"}),
    )
    nickname = forms.CharField(label="닉네임", max_length=30)
    measured_on = forms.DateField(label="측정일", initial=date.today, widget=forms.DateInput(attrs={"class": "input", "type": "date"}))

    class Meta:
        model = Profile
        fields = (
            "area", "age", "gender", "accessibility_type", "height_cm", "weight_kg",
            "avatar_preference", "rank_participation",
        )
        widgets = {
            "area": forms.Select(attrs={"class": "input"}),
            "age": forms.NumberInput(attrs={"class": "input", "min": 1, "max": 120}),
            "gender": forms.Select(attrs={"class": "input"}),
            "accessibility_type": forms.Select(attrs={"class": "input"}),
            "height_cm": forms.NumberInput(attrs={"class": "input bmi-input", "min": 50, "step": "0.1"}),
            "weight_kg": forms.NumberInput(attrs={"class": "input bmi-input", "min": 10, "step": "0.1"}),
            "avatar_preference": forms.Select(attrs={"class": "input"}),
            "rank_participation": forms.CheckboxInput(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Accept legacy submitted values while showing only four mascots.
        if self.is_bound:
            self.data = self.data.copy()
            key = self.add_prefix("avatar_preference")
            if self.data.get(key) in ("AUTO", "SLIM"):
                self.data[key] = "ACTIVE"
        elif self.initial.get("avatar_preference") in (None, "AUTO", "SLIM"):
            self.initial["avatar_preference"] = "ACTIVE"
        labels = {
            "area": "활동 지역", "age": "나이", "gender": "성별",
            "accessibility_type": "장애 여부",
            "height_cm": "키 (cm)", "weight_kg": "몸무게 (kg)",
            "avatar_preference": "마스코트 선택",
            "rank_participation": "랭킹 참여",
        }
        for field_name, label in labels.items():
            self.fields[field_name].label = label
        self.fields["accessibility_type"].required = False
        if user:
            self.fields["nickname"].initial = "" if needs_kakao_nickname(user) else user.username
            self.fields["nickname"].widget.attrs["placeholder"] = "사용할 별명을 입력하세요"

    def clean_nickname(self):
        nickname = self.cleaned_data["nickname"].strip()
        exists = User.objects.filter(username__iexact=nickname).exclude(pk=self.user.pk).exists()
        if exists:
            raise forms.ValidationError("이미 사용 중인 닉네임입니다.")
        return nickname

    def clean_accessibility_type(self):
        return self.cleaned_data.get("accessibility_type") or "NON_DISABLED"

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.user.username = self.cleaned_data["nickname"]
        profile.user.save()
        if commit:
            profile.save()
        return profile


class FriendForm(forms.Form):
    friend_code = forms.CharField(
        label="친구 코드 또는 닉네임",
        max_length=30,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "예: 운동친구01"}),
    )
