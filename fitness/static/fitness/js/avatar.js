function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function drawAvatar(canvas) {
  const context = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 320;
  const height = canvas.clientHeight || 360;

  canvas.width = width * ratio;
  canvas.height = height * ratio;
  context.scale(ratio, ratio);
  context.clearRect(0, 0, width, height);

  const heightCm = Number(canvas.dataset.height) || 165;
  const weightKg = Number(canvas.dataset.weight) || 60;
  const muscleKg = Number(canvas.dataset.muscle) || 22;
  const bodyFat = Number(canvas.dataset.fat) || 25;
  const age = Number(canvas.dataset.age) || 25;
  const level = Number(canvas.dataset.level) || 1;
  const gender = canvas.dataset.gender || "N";

  const bmi = weightKg / ((heightCm / 100) ** 2);
  const fullness = clamp((bmi - 18) / 13 + (bodyFat - 18) / 70, 0, 1);
  const muscle = clamp((muscleKg / weightKg - 0.22) / 0.23, 0, 1);
  const isSenior = age >= 60;
  const isFemale = gender === "F";

  const cx = width / 2;
  const ground = height - 26;
  const scale = clamp(heightCm / 170, 0.86, 1.12);
  const headRadius = 31 * scale;
  const shoulder = (47 + muscle * 20 + fullness * 10) * scale;
  const torsoWidth = (45 + fullness * 22 + muscle * 11) * scale;
  const limbWidth = (13 + fullness * 5 + muscle * 6) * scale;
  const torsoHeight = (88 - fullness * 4) * scale;
  const skin = isFemale ? "#f4c5a6" : "#e8b28c";
  const hair = isSenior ? "#bdc1c0" : (isFemale ? "#503625" : "#33271f");
  const shirt = level >= 15 ? "#6a3d91" : level >= 5 ? "#176f65" : "#2e6e9f";
  const pants = level >= 25 ? "#3e254d" : "#243753";

  function ellipse(x, y, rx, ry, color) {
    context.fillStyle = color;
    context.beginPath();
    context.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
    context.fill();
  }

  function line(x1, y1, x2, y2, widthValue, color) {
    context.strokeStyle = color;
    context.lineWidth = widthValue;
    context.lineCap = "round";
    context.beginPath();
    context.moveTo(x1, y1);
    context.lineTo(x2, y2);
    context.stroke();
  }

  ellipse(cx, ground + 3, 58, 9, "rgba(39, 43, 34, 0.22)");

  // 다리와 신발
  const hipY = ground - 120 * scale;
  const kneeY = ground - 60 * scale;
  line(cx - torsoWidth * 0.28, hipY, cx - torsoWidth * 0.45, kneeY, limbWidth + 5, pants);
  line(cx - torsoWidth * 0.45, kneeY, cx - torsoWidth * 0.57, ground - 18, limbWidth + 3, pants);
  line(cx + torsoWidth * 0.28, hipY, cx + torsoWidth * 0.45, kneeY, limbWidth + 5, pants);
  line(cx + torsoWidth * 0.45, kneeY, cx + torsoWidth * 0.57, ground - 18, limbWidth + 3, pants);
  ellipse(cx - torsoWidth * 0.62, ground - 13, 20 * scale, 8 * scale, "#f6f7f4");
  ellipse(cx + torsoWidth * 0.62, ground - 13, 20 * scale, 8 * scale, "#f6f7f4");

  // 몸통
  context.fillStyle = shirt;
  context.beginPath();
  context.roundRect(cx - torsoWidth, hipY - torsoHeight, torsoWidth * 2, torsoHeight, 20 * scale);
  context.fill();
  ellipse(cx, hipY - torsoHeight + 4, shoulder, 20 * scale, shirt);

  // 팔
  const shoulderY = hipY - torsoHeight + 25 * scale;
  line(cx - shoulder, shoulderY, cx - shoulder - 21 * scale, hipY - 14 * scale, limbWidth, skin);
  line(cx - shoulder - 21 * scale, hipY - 14 * scale, cx - shoulder - 5 * scale, hipY + 18 * scale, limbWidth - 2, skin);
  line(cx + shoulder, shoulderY, cx + shoulder + 21 * scale, hipY - 14 * scale, limbWidth, skin);
  line(cx + shoulder + 21 * scale, hipY - 14 * scale, cx + shoulder + 5 * scale, hipY + 18 * scale, limbWidth - 2, skin);

  // 목과 머리
  line(cx, shoulderY - 5, cx, shoulderY - 23 * scale, 15 * scale, skin);
  const headY = shoulderY - 60 * scale;
  ellipse(cx, headY, headRadius, headRadius * 1.08, skin);
  ellipse(cx, headY - 17 * scale, headRadius + 2, headRadius * 0.58, hair);
  if (isFemale) {
    line(cx - headRadius, headY - 10, cx - headRadius - 15 * scale, headY + 32 * scale, 13 * scale, hair);
    line(cx + headRadius, headY - 10, cx + headRadius + 15 * scale, headY + 32 * scale, 13 * scale, hair);
  }
  if (level >= 5) {
    context.fillStyle = "#c8f07f";
    context.fillRect(cx - headRadius, headY - 15 * scale, headRadius * 2, 7 * scale);
  }

  // 얼굴
  context.fillStyle = "#34251e";
  ellipse(cx - 11 * scale, headY + 3 * scale, 2.2 * scale, 3 * scale, "#34251e");
  ellipse(cx + 11 * scale, headY + 3 * scale, 2.2 * scale, 3 * scale, "#34251e");
  context.strokeStyle = "#b65854";
  context.lineWidth = 2 * scale;
  context.beginPath();
  context.arc(cx, headY + 12 * scale, 7 * scale, 0.2, Math.PI - 0.2);
  context.stroke();

  // 레벨별 장식
  if (level >= 15) {
    context.fillStyle = "#f5cf54";
    context.beginPath();
    context.arc(cx + shoulder + 8, shoulderY + 16, 10 * scale, 0, Math.PI * 2);
    context.fill();
  }
  if (level >= 25) {
    context.strokeStyle = "rgba(255, 234, 139, 0.95)";
    context.lineWidth = 3;
    context.beginPath();
    context.arc(cx, headY, headRadius + 13, 0, Math.PI * 2);
    context.stroke();
  }
}

function redrawAllAvatars() {
  document.querySelectorAll("[data-avatar-canvas]").forEach(drawAvatar);
}

window.addEventListener("resize", redrawAllAvatars);
window.addEventListener("load", redrawAllAvatars);
