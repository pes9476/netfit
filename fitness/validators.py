from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


MAX_PROOF_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_PROOF_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_proof_image(upload):
    if not upload:
        return
    if upload.size > MAX_PROOF_IMAGE_SIZE:
        raise ValidationError("인증 사진은 5MB 이하만 업로드할 수 있습니다.")
    if getattr(upload, "content_type", "") not in ALLOWED_PROOF_IMAGE_TYPES:
        raise ValidationError("인증 사진은 JPEG, PNG, WebP 형식만 사용할 수 있습니다.")
    try:
        image = Image.open(upload)
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("올바른 이미지 파일을 선택해 주세요.")
    finally:
        upload.seek(0)
