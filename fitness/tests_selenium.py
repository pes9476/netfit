"""
Selenium은 동적 페이지를 수집할 때도 쓸 수 있지만,
이 프로젝트에서는 로그인과 운동 기록 화면이 실제로 동작하는지 확인하는 자동 테스트 용도로 사용합니다.
ChromeDriver 설치 후 다음처럼 실행합니다.
python manage.py test fitness.tests_selenium
"""
from django.test import LiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By

class LoginPageTest(LiveServerTestCase):
    def setUp(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        self.browser = webdriver.Chrome(options=options)

    def tearDown(self):
        self.browser.quit()

    def test_login_page_title(self):
        self.browser.get(f"{self.live_server_url}/login/")
        self.assertIn("핏배틀", self.browser.title)
        self.assertTrue(self.browser.find_element(By.TAG_NAME, "form"))
