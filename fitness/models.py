from django.conf import settings
from django.db import models

REGION_CHOICES = [
    ("서울특별시", "서울특별시"), ("부산광역시", "부산광역시"),
    ("대구광역시", "대구광역시"), ("인천광역시", "인천광역시"),
    ("광주광역시", "광주광역시"), ("대전광역시", "대전광역시"),
    ("울산광역시", "울산광역시"), ("세종특별자치시", "세종특별자치시"),
    ("경기도", "경기도"), ("강원특별자치도", "강원특별자치도"),
    ("충청북도", "충청북도"), ("충청남도", "충청남도"),
    ("전북특별자치도", "전북특별자치도"), ("전라남도", "전라남도"),
    ("경상북도", "경상북도"), ("경상남도", "경상남도"),
    ("제주특별자치도", "제주특별자치도"),
]

class Profile(models.Model):
    GENDER_CHOICES = [("M", "남성"), ("F", "여성"), ("N", "선택 안 함")]
    AVATAR_CHOICES = [
        ("AUTO", "자동 추천"), ("SLIM", "날씬형"), ("BALANCED", "균형형"),
        ("SOFT", "통통형"), ("ACTIVE", "활동형"), ("MUSCULAR", "강한 운동형"),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    area = models.CharField(max_length=20, choices=REGION_CHOICES, default="서울특별시")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default="N")
    age = models.PositiveIntegerField(null=True, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    skeletal_muscle_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    body_fat_percent = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    avatar_preference = models.CharField(max_length=10, choices=AVATAR_CHOICES, default="AUTO")
    rank_participation = models.BooleanField(default=True)

    @property
    def bmi(self):
        if not self.height_cm or not self.weight_kg:
            return None
        height_m = float(self.height_cm) / 100
        return round(float(self.weight_kg) / (height_m ** 2), 1)

    @property
    def body_style(self):
        if self.avatar_preference != "AUTO":
            return self.avatar_preference
        if self.skeletal_muscle_kg and self.weight_kg:
            muscle_ratio = float(self.skeletal_muscle_kg) / float(self.weight_kg) * 100
            cutoff = 38 if self.gender == "M" else 31
            if muscle_ratio >= cutoff:
                return "MUSCULAR"
        if not self.bmi:
            return "BALANCED"
        if self.bmi < 18.5:
            return "SLIM"
        if self.bmi < 23:
            return "BALANCED"
        return "SOFT"

    @property
    def bmi_status(self):
        if not self.bmi:
            return "키와 몸무게를 입력해주세요"
        if self.bmi < 18.5:
            return "저체중 참고 범위 · 날씬형"
        if self.bmi < 23:
            return "정상 참고 범위 · 균형형"
        if self.bmi < 25:
            return "과체중 참고 범위 · 통통형"
        return "비만 참고 범위 · 통통형"

    @property
    def age_group(self):
        if self.age and self.age < 18:
            return "child"
        if self.age and self.age >= 60:
            return "senior"
        return "adult"

    @property
    def sprite_gender(self):
        return "female" if self.gender == "F" else "male"

    @property
    def character_variant(self):
        return f"{self.sprite_gender}-{self.age_group}-{self.body_style.lower()}"

    @property
    def character_label(self):
        labels = {
            "SLIM": "날렵한 새싹", "BALANCED": "균형 잡힌 챌린저",
            "SOFT": "꾸준한 챌린저", "ACTIVE": "활동적인 운동가",
            "MUSCULAR": "파워 트레이너",
        }
        return labels[self.body_style]

class CharacterCard(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    level = models.PositiveIntegerField(default=1)
    xp = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=30, default="러닝 새싹")
    frame = models.CharField(max_length=20, default="새싹")

    @property
    def next_level_xp(self):
        return 300 + (self.level - 1) * 100

    @property
    def card_tier(self):
        if self.level >= 25:
            return "마스터"
        if self.level >= 15:
            return "골드"
        if self.level >= 5:
            return "실버"
        return "새싹"


class BodyMeasurement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="body_measurements")
    measured_on = models.DateField()
    height_cm = models.DecimalField(max_digits=5, decimal_places=1)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1)
    skeletal_muscle_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    body_fat_percent = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-measured_on", "-created_at"]

    @property
    def bmi(self):
        height_m = float(self.height_cm) / 100
        return round(float(self.weight_kg) / (height_m ** 2), 1) if height_m else None

class WorkoutRecord(models.Model):
    WORKOUT_CHOICES = [
        ("러닝", "러닝"), ("걷기", "걷기"), ("헬스", "헬스"),
        ("자전거", "자전거"), ("수영", "수영"), ("배드민턴", "배드민턴"),
        ("기타", "기타"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    workout_type = models.CharField(max_length=10, choices=WORKOUT_CHOICES)
    minutes = models.PositiveIntegerField()
    distance_km = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    location = models.CharField(max_length=120, blank=True)
    with_party = models.BooleanField(default=False)
    earned_xp = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class Facility(models.Model):
    name = models.CharField(max_length=200)
    facility_type = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=30, choices=REGION_CHOICES)
    address = models.CharField(max_length=250, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    homepage_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

class Party(models.Model):
    name = models.CharField(max_length=100)
    goal_km = models.PositiveIntegerField(default=100)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="parties")


class FriendLink(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_friend_links")
    friend = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_friend_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "friend"], name="unique_friend_link")]

class CardBattle(models.Model):
    SCOPE_CHOICES = [("PARTY", "파티원 배틀"), ("REGION", "지역 카드 배틀")]
    REWARD_CHOICES = [
        ("NONE", "보상 없음"), ("COFFEE", "커피 사기 ☕"), ("MEAL", "밥 사기 🍚"),
        ("CHICKEN", "치킨 사기 🍗"), ("CAFE", "카페 디저트 사기 🍰"),
        ("MOVIE", "영화 보여주기 🎬"), ("CUSTOM", "직접 입력"),
    ]
    challenger = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES)
    opponent_name = models.CharField(max_length=80)
    opponent_level = models.PositiveIntegerField(default=1)
    region_name = models.CharField(max_length=30, blank=True)
    reward = models.CharField(max_length=10, choices=REWARD_CHOICES, default="NONE")
    custom_reward = models.CharField(max_length=100, blank=True)
    challenger_power = models.PositiveIntegerField(default=0)
    opponent_power = models.PositiveIntegerField(default=0)
    is_finished = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def reward_label(self):
        return self.custom_reward if self.reward == "CUSTOM" else self.get_reward_display()
