import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Beautiful Soup 예시: 시설 홈페이지에서 제목과 운영시간 후보 문구를 확인합니다."

    def add_arguments(self, parser):
        parser.add_argument("url")

    def handle(self, *args, **options):
        response = requests.get(options["url"], timeout=10, headers={"User-Agent": "FitBattleStudyBot/1.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else "제목 없음"
        text = soup.get_text(" ", strip=True)
        keywords = [word for word in text.split() if "운영" in word or "시간" in word][:10]
        self.stdout.write(f"페이지 제목: {title}")
        self.stdout.write(f"운영시간 관련 후보: {keywords}")
