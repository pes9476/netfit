from django.test import TestCase, Client
from django.contrib.auth.models import User
from fitness.services import interpret_weather_code, get_weather_data
from fitness.models import Profile


class WeatherLogicTests(TestCase):
    def test_interpret_weather_code_rain(self):
        cond, icon, color, msg = interpret_weather_code(code=61, temp=18.0, precip=1.5)
        self.assertEqual(cond, "비")
        self.assertIn("fa-cloud-showers-heavy", icon)

    def test_interpret_weather_code_drizzle(self):
        cond, icon, color, msg = interpret_weather_code(code=51, temp=17.0, precip=0.2)
        self.assertEqual(cond, "이슬비")

    def test_interpret_weather_code_shower(self):
        cond, icon, color, msg = interpret_weather_code(code=80, temp=22.0, precip=2.0)
        self.assertEqual(cond, "소나기")

    def test_interpret_weather_code_thunder(self):
        cond, icon, color, msg = interpret_weather_code(code=95, temp=20.0)
        self.assertEqual(cond, "뇌우")

    def test_interpret_weather_code_clear_day(self):
        cond, icon, color, msg = interpret_weather_code(code=0, temp=20.0, cloud_cover=10, is_day=1)
        self.assertEqual(cond, "맑음")
        self.assertEqual(icon, "fa-sun")

    def test_interpret_weather_code_clear_night(self):
        cond, icon, color, msg = interpret_weather_code(code=0, temp=15.0, cloud_cover=10, is_day=0)
        self.assertEqual(cond, "맑음")
        self.assertEqual(icon, "fa-moon")

    def test_interpret_weather_code_partly_cloudy(self):
        cond, icon, color, msg = interpret_weather_code(code=1, temp=19.0, cloud_cover=35, is_day=1)
        self.assertEqual(cond, "대체로 맑음")

    def test_interpret_weather_code_cloudy(self):
        cond, icon, color, msg = interpret_weather_code(code=2, temp=19.0, cloud_cover=60, is_day=1)
        self.assertEqual(cond, "구름 많음")

    def test_interpret_weather_code_overcast(self):
        cond, icon, color, msg = interpret_weather_code(code=3, temp=18.0, cloud_cover=90, is_day=1)
        self.assertEqual(cond, "흐림")

    def test_get_weather_data_structure(self):
        data = get_weather_data(lat=37.2636, lon=127.0286, location_name="수원시 인계동", is_gps=True, force_refresh=True)
        self.assertIn("temperature", data)
        self.assertIn("apparent_temperature", data)
        self.assertIn("condition", data)
        self.assertIn("windspeed", data)
        self.assertIn("color", data)
        self.assertIn("icon", data)
        self.assertEqual(data["location_name"], "수원시 인계동")

    def test_weather_api_endpoint(self):
        client = Client()
        user = User.objects.create_user(username="weathertest", password="password123")
        profile = user.profile
        profile.area = "경기도 수원시"
        profile.save()
        client.login(username="weathertest", password="password123")

        response = client.get("/api/weather/?lat=37.2636&lng=127.0286&loc_name=수원시&refresh=true")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["status"], "success")
        self.assertIn("weather", json_data)
        self.assertIn("condition", json_data["weather"])
