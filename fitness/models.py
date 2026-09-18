import urllib.parse
from django.conf import settings
from django.db import models
from django.utils import timezone

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

class KakaoAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kakao_id = models.CharField(max_length=64, unique=True)


def needs_kakao_nickname(user):
    return (
        user.username.startswith("kakao_") and len(user.username) == 38
        and KakaoAccount.objects.filter(user=user).exists()
    )


class Profile(models.Model):
    @property
    def display_name(self):
        # 임시 카카오 ID는 인증용이며 공개 닉네임이 아니다.
        # 빈 이름은 화면에서 생략하고, 프로필의 닉네임 저장 후 표시한다.
        return "" if needs_kakao_nickname(self.user) else self.user.username

    GENDER_CHOICES = [("M", "남성"), ("F", "여성"), ("N", "선택 안 함")]
    AVATAR_CHOICES = [
        ("AUTO", "자동 추천"), ("SLIM", "날씬형"), ("BALANCED", "균형형"),
        ("SOFT", "통통형"), ("ACTIVE", "활동형"), ("MUSCULAR", "강한 운동형"),
    ]
    GOAL_CHOICES = [
        ("HEALTH", "건강 습관"), ("DIET", "체중 관리"),
        ("STRENGTH", "근력 향상"), ("ENDURANCE", "체력 향상"),
    ]
    MODE_CHOICES = [("SOLO", "혼자 운동"), ("GROUP", "그룹 운동")]
    ACCESSIBILITY_CHOICES = [("NON_DISABLED", "비장애인"), ("DISABLED", "장애인")]
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
    ACTIVITY_MODE_CHOICES = [("UNSET", "미선택"), ("SOLO", "솔로"), ("GROUP", "그룹")]
    DISABILITY_CHOICES = [("UNSET", "응답 안 함"), ("NONE", "비장애인"), ("DISABLED", "장애인")]
    WHEELCHAIR_CHOICES = [("UNSET", "응답 안 함"), ("NO", "이용하지 않음"), ("OPTIONAL", "상황에 따라 이용"), ("REQUIRED", "필수")]
    onboarding_completed = models.BooleanField(default=False)
    preferred_activity_mode = models.CharField(max_length=8, choices=ACTIVITY_MODE_CHOICES, default="UNSET")
    disability_status = models.CharField(max_length=10, choices=DISABILITY_CHOICES, default="UNSET")
    wheelchair_usage = models.CharField(max_length=10, choices=WHEELCHAIR_CHOICES, default="UNSET")
    workout_goal = models.CharField(max_length=12, choices=GOAL_CHOICES, blank=True)
    workout_days = models.PositiveSmallIntegerField(default=3)
    workout_mode = models.CharField(max_length=8, choices=MODE_CHOICES, blank=True)
    onboarding_completed = models.BooleanField(default=False)
    accessibility_type = models.CharField(
        max_length=12, choices=ACCESSIBILITY_CHOICES, default="NON_DISABLED",
    )
    equipped_outfit = models.CharField(
        max_length=120,
        blank=True,
        default="NONE",
    )

    @property
    def equipped_outfits_list(self):
        if not self.equipped_outfit or self.equipped_outfit == "NONE":
            return []
        return [c.strip() for c in self.equipped_outfit.split(",") if c.strip() and c.strip() != "NONE"]

    def is_outfit_equipped(self, code):
        return code in self.equipped_outfits_list

    def equip_outfit(self, code):
        current = self.equipped_outfits_list
        if code not in current:
            current.append(code)
        self.equipped_outfit = ",".join(current) if current else "NONE"

    def unequip_outfit(self, code=None):
        if not code:
            self.equipped_outfit = "NONE"
        else:
            current = [c for c in self.equipped_outfits_list if c != code]
            self.equipped_outfit = ",".join(current) if current else "NONE"

    @property
    def recommended_course(self):
        courses = {
            "HEALTH": ("꾸준한 밸런스 코스", "빠르게 걷기 30분 + 전신 스트레칭 10분"),
            "DIET": ("활력 다이어트 코스", "인터벌 걷기·러닝 35분 + 코어 운동 15분"),
            "STRENGTH": ("파워 업 코스", "전신 근력 운동 45분 + 가벼운 유산소 10분"),
            "ENDURANCE": ("지구력 챌린지 코스", "러닝·자전거·수영 중 45분 + 회복 스트레칭"),
        }
        return courses.get(self.workout_goal, courses["HEALTH"])

    @property
    def bmi(self):
        if not self.height_cm or not self.weight_kg:
            return None
        height_m = float(self.height_cm) / 100
        return round(float(self.weight_kg) / (height_m ** 2), 1)

    @property
    def body_style(self):
        # Legacy storage values are retained; appearance is now manual only.
        # AUTO/SLIM and older unknown values resolve to the default tiger.
        return {
            "BALANCED": "BALANCED", "SOFT": "SOFT",
            "MUSCULAR": "MUSCULAR", "ACTIVE": "ACTIVE",
        }.get(self.avatar_preference, "ACTIVE")

    @property
    def bmi_status(self):
        if not self.bmi:
            return "키와 몸무게를 입력해주세요"
        if self.bmi < 18.5:
            return "저체중 참고 범위"
        if self.bmi < 23:
            return "정상 참고 범위"
        if self.bmi < 25:
            return "과체중 참고 범위"
        return "비만 참고 범위"

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
            "SLIM": "백호", "BALANCED": "아기공룡",
            "SOFT": "햄스터", "ACTIVE": "백호",
            "MUSCULAR": "백곰",
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
        ("러닝", "러닝"), ("만보", "만보"), ("걷기", "산책"), ("헬스", "헬스"),
        ("자전거", "자전거"), ("수영", "수영"), ("배드민턴", "배드민턴"),
        ("등산", "등산"), ("축구", "축구"), ("농구", "농구"), ("요가", "요가"),
        ("기타", "기타"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    workout_type = models.CharField(max_length=10, choices=WORKOUT_CHOICES)
    custom_workout_name = models.CharField(max_length=50, blank=True)
    minutes = models.PositiveIntegerField()
    distance_km = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    location = models.CharField(max_length=120, blank=True)
    with_party = models.BooleanField(default=False)
    proof_image = models.ImageField(upload_to="workout_proofs/", blank=True, null=True)
    earned_xp = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def workout_name(self):
        if self.workout_type == "기타" and self.custom_workout_name:
            return self.custom_workout_name
        if self.workout_type == "걷기":
            return "산책"
        return self.get_workout_type_display()

    @property
    def calories_burned(self):
        return int(self.minutes * 8.5) if self.minutes else 0


class BadgeAward(models.Model):
    BRONZE = "BRONZE"
    SILVER = "SILVER"
    GOLD = "GOLD"
    BADGE_CHOICES = [(GOLD, "금"), (SILVER, "은"), (BRONZE, "동")]
    POINTS = {GOLD: 100, SILVER: 50, BRONZE: 30}
    SOURCE_CHOICES = [("WORKOUT", "운동 기록"), ("DAILY_QUEST", "일퀘 완료")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badge_awards")
    badge_type = models.CharField(max_length=8, choices=BADGE_CHOICES)
    points = models.PositiveSmallIntegerField()
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES)
    workout_record = models.OneToOneField(
        WorkoutRecord, null=True, blank=True, on_delete=models.CASCADE, related_name="badge_award",
    )
    daily_quest = models.ForeignKey(
        "DailyQuest", null=True, blank=True, on_delete=models.CASCADE, related_name="badge_awards",
    )
    personal_quest = models.ForeignKey(
        "PersonalDailyQuest", null=True, blank=True, on_delete=models.CASCADE, related_name="badge_awards",
    )
    proof_image = models.ImageField(upload_to="quest_proofs/", blank=True, null=True)
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-awarded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "daily_quest"],
                condition=models.Q(daily_quest__isnull=False),
                name="unique_group_quest_badge_per_user",
            ),
            models.UniqueConstraint(
                fields=["user", "personal_quest"],
                condition=models.Q(personal_quest__isnull=False),
                name="unique_personal_quest_badge_per_user",
            ),
        ]

    @classmethod
    def badge_for_minutes(cls, minutes):
        if minutes >= 90:
            return cls.GOLD
        if minutes >= 60:
            return cls.SILVER
        if minutes >= 30:
            return cls.BRONZE
        return cls.BRONZE

    def save(self, *args, **kwargs):
        self.points = self.POINTS[self.badge_type]
        super().save(*args, **kwargs)


class OutfitPurchase(models.Model):
    OUTFIT_CHOICES = [
        ("BAND", "스포티 네온 헤어밴드"),
        ("GLASS", "사이버 네온 선글라스"),
        ("HEADSET", "사이버 게이밍 헤드셋"),
        ("MASK", "사이버 닌자 마스크"),
        ("BELT", "골드 챔피언 벨트"),
        ("CAP", "운동 모자"),
        ("MEDAL", "골드 빅토리 목걸이"),
        ("GLOVES", "파이어 복싱 글러브"),
        ("SPORT", "스포츠 유니폼"),
        ("CLOAK", "다크 히어로 망토"),
        ("SWORD", "네온 빔세이버"),
        ("CROWN", "챔피언 왕관"),
        ("WING", "사이버 홀로그램 윙"),
        ("DRAGON", "미니 파이어 펫"),
        ("AURA", "불꽃 버닝 파이어 오라"),
        ("VICTORY", "골드 빅토리 트로피"),
    ]
    COSTS = {
        "BAND": 50,
        "GLASS": 80,
        "HEADSET": 100,
        "MASK": 110,
        "BELT": 120,
        "CAP": 150,
        "MEDAL": 180,
        "GLOVES": 200,
        "SPORT": 250,
        "CLOAK": 300,
        "SWORD": 350,
        "CROWN": 400,
        "WING": 500,
        "DRAGON": 550,
        "AURA": 650,
        "VICTORY": 800,
    }
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="outfit_purchases")
    outfit = models.CharField(max_length=10, choices=OUTFIT_CHOICES)
    cost = models.PositiveIntegerField()
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "outfit"], name="unique_user_outfit")]

    def save(self, *args, **kwargs):
        self.cost = self.COSTS[self.outfit]
        super().save(*args, **kwargs)

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

    @property
    def naver_map_url(self):
        if hasattr(self, "_naver_map_url"):
            return self._naver_map_url
        if hasattr(self, "naver_directions_url"):
            return self.naver_directions_url
        if self.latitude and self.longitude:
            encoded_name = urllib.parse.quote(self.name)
            return f"https://map.naver.com/p/directions/-/{self.longitude},{self.latitude},{encoded_name},PLACE_POI/-/transit"
        if self.address:
            return f"https://map.naver.com/p/search/{urllib.parse.quote(self.address)}"
        return f"https://map.naver.com/p/search/{urllib.parse.quote(self.name)}"

    @naver_map_url.setter
    def naver_map_url(self, value):
        self._naver_map_url = value

    @property
    def kakao_map_url(self):
        if hasattr(self, "_kakao_map_url"):
            return self._kakao_map_url
        if self.latitude and self.longitude:
            encoded_name = urllib.parse.quote(self.name)
            return f"https://map.kakao.com/link/to/{encoded_name},{self.latitude},{self.longitude}"
        if self.address:
            return f"https://map.kakao.com/link/search/{urllib.parse.quote(self.address)}"
        return f"https://map.kakao.com/link/search/{urllib.parse.quote(self.name)}"

    @kakao_map_url.setter
    def kakao_map_url(self, value):
        self._kakao_map_url = value

class Party(models.Model):
    name = models.CharField(max_length=100)
    goal_km = models.PositiveIntegerField(default=100)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="parties")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_parties", null=True)
    max_members = models.PositiveSmallIntegerField(default=4)
    created_at = models.DateTimeField(default=timezone.now)
    challenge_start = models.DateField(null=True, blank=True)
    challenge_end = models.DateField(null=True, blank=True)
    challenge_reward = models.CharField(max_length=200, blank=True)


class Mission(models.Model):
    MODE_CHOICES = [("SOLO", "데일리 미션"), ("GROUP", "그룹 미션")]
    STATUS_CHOICES = [("DRAFT", "준비"), ("ACTIVE", "진행"), ("FINISHED", "종료")]
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_missions")
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name="missions", null=True, blank=True)
    mode = models.CharField(max_length=8, choices=MODE_CHOICES)
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    target_count = models.PositiveIntegerField(default=1)
    requires_photo = models.BooleanField(default=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ACTIVE")
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, through="MissionParticipant", related_name="missions")
    created_at = models.DateTimeField(auto_now_add=True)


class MissionParticipant(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="participations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mission_participations")
    progress_count = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["mission", "user"], name="unique_mission_participant")]


class BattleRoom(models.Model):
    SIZE_CHOICES = [(2, "1대1"), (4, "2대2")]
    STATUS_CHOICES = [("RECRUITING", "모집"), ("ACTIVE", "진행"), ("FINISHED", "종료"), ("CANCELLED", "취소")]
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_battle_rooms")
    mission = models.OneToOneField(Mission, on_delete=models.PROTECT, related_name="battle_room")
    title = models.CharField(max_length=120)
    capacity = models.PositiveSmallIntegerField(choices=SIZE_CHOICES)
    penalty = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="RECRUITING")
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, through="BattleParticipant", related_name="battle_rooms")
    created_at = models.DateTimeField(auto_now_add=True)


class BattleParticipant(models.Model):
    battle = models.ForeignKey(BattleRoom, on_delete=models.CASCADE, related_name="entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="battle_entries")
    team = models.PositiveSmallIntegerField(default=1)
    score = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["battle", "user"], name="unique_battle_participant")]


class ProofSubmission(models.Model):
    STATUS_CHOICES = [("PENDING", "검토 대기"), ("APPROVED", "승인"), ("REJECTED", "반려")]
    participant = models.ForeignKey(MissionParticipant, on_delete=models.CASCADE, related_name="proofs")
    photo = models.ImageField(upload_to="proofs/%Y/%m/%d/")
    captured_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)

class DailyQuest(models.Model):
    SOURCE_CHOICES = [("DIRECT", "직접 입력"), ("AI", "AI 추천"), ("SYSTEM", "시스템")]
    PERIOD_CHOICES = [("DAILY", "일일"), ("WEEKLY", "주간")]
    CATEGORY_CHOICES = [
        ("ATTENDANCE", "출석 체크"),
        ("WORKOUT", "협동 운동"),
        ("FACILITY", "주변 시설"),
        ("CUMULATIVE", "주간 누적"),
    ]
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name="daily_quests")
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="created_daily_quests",
        null=True, blank=True,
    )
    title = models.CharField(max_length=100)
    workout_type = models.CharField(
        max_length=10,
        choices=[choice for choice in WorkoutRecord.WORKOUT_CHOICES if choice[0] != "만보"],
        default="기타",
        blank=True,
    )
    custom_workout_name = models.CharField(max_length=50, blank=True)
    target_minutes = models.PositiveIntegerField(default=0)
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES, default="DAILY")
    mission_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="WORKOUT")
    target_count = models.PositiveIntegerField(default=1)
    current_progress = models.PositiveIntegerField(default=0)
    facility = models.ForeignKey(
        "Facility", null=True, blank=True, on_delete=models.SET_NULL, related_name="party_quests",
    )
    week_start = models.DateField(null=True, blank=True)
    reward_points = models.PositiveIntegerField(default=30)
    description = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=8, choices=SOURCE_CHOICES, default="AI")
    quest_date = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-quest_date", "-created_at"]

    @property
    def workout_label(self):
        if self.workout_type == "기타" and self.custom_workout_name:
            return self.custom_workout_name
        return "산책" if self.workout_type == "걷기" else self.get_workout_type_display()


class AttendanceRecord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendances")
    date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="unique_user_daily_attendance")
        ]


class PersonalDailyQuest(models.Model):
    SOURCE_CHOICES = [("DIRECT", "직접 입력"), ("AI", "AI 추천"), ("SYSTEM", "시스템")]
    PERIOD_CHOICES = [("DAILY", "일일"), ("WEEKLY", "주간")]
    CATEGORY_CHOICES = [
        ("ATTENDANCE", "출석 체크"),
        ("WORKOUT", "운동 수행"),
        ("FACILITY", "주변 시설"),
        ("CUMULATIVE", "주간 누적"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="personal_daily_quests",
    )
    title = models.CharField(max_length=100)
    workout_type = models.CharField(
        max_length=10,
        choices=[choice for choice in WorkoutRecord.WORKOUT_CHOICES if choice[0] != "만보"],
        default="기타",
        blank=True,
    )
    custom_workout_name = models.CharField(max_length=50, blank=True)
    target_minutes = models.PositiveIntegerField(default=0)
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES, default="DAILY")
    mission_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="WORKOUT")
    target_count = models.PositiveIntegerField(default=1)
    current_progress = models.PositiveIntegerField(default=0)
    facility = models.ForeignKey(
        "Facility", null=True, blank=True, on_delete=models.SET_NULL, related_name="quests",
    )
    week_start = models.DateField(null=True, blank=True)
    reward_points = models.PositiveIntegerField(default=30)
    description = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=8, choices=SOURCE_CHOICES, default="DIRECT")
    quest_date = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-quest_date", "-created_at"]

    @property
    def workout_label(self):
        if self.mission_category == "ATTENDANCE":
            return "출석 체크"
        if self.workout_type == "기타" and self.custom_workout_name:
            return self.custom_workout_name
        return "산책" if self.workout_type == "걷기" else self.get_workout_type_display()


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


class FriendRequest(models.Model):
    STATUS_CHOICES = [("PENDING", "대기중"), ("ACCEPTED", "수락됨"), ("REJECTED", "거절됨")]
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_friend_requests")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_friend_requests")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    sender_viewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PartyInvitation(models.Model):
    STATUS_CHOICES = [("PENDING", "대기중"), ("ACCEPTED", "수락됨"), ("REJECTED", "거절됨")]
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name="invitations")
    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_party_invitations")
    invitee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_party_invitations")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    inviter_viewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

