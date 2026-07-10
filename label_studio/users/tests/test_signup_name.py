"""회원가입 시 받는 본명(`name`) — 이메일 외의 식별 수단.

`User.first_name` 한 칸에 저장하므로 `get_full_name()` 을 쓰는 모든 화면
(정산, 작업 내역, 아바타 이니셜, 사용자 목록)이 자동으로 본명을 쓴다.
"""

import re

import pytest
from django.test import Client
from users.models import User

SIGNUP_URL = '/user/signup/'


def _csrf(client):
    page = client.get(SIGNUP_URL)
    assert page.status_code == 200
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())
    assert match, 'csrf token not rendered'
    return match.group(1)


@pytest.fixture(autouse=True)
def open_signup(settings):
    # `.env` 의 DISABLE_SIGNUP_WITHOUT_LINK 게이트만 열고, 폼 검증은 그대로 둔다.
    settings.DISABLE_SIGNUP_WITHOUT_LINK = False


@pytest.mark.django_db
def test_signup_stores_real_name():
    client = Client()
    response = client.post(
        SIGNUP_URL,
        {
            'csrfmiddlewaretoken': _csrf(client),
            'email': 'hong@example.com',
            'name': '홍길동',
            'password': 'Str0ngPass!23',
        },
    )
    assert response.status_code == 302, response.content[:300]

    user = User.objects.get(email='hong@example.com')
    assert user.first_name == '홍길동'
    assert user.last_name == ''
    # 성/이름으로 쪼개지 않으므로 공백이 끼지 않는다.
    assert user.get_full_name() == '홍길동'
    assert user.name_or_email() == '홍길동'


@pytest.mark.django_db
def test_signup_requires_name():
    client = Client()
    response = client.post(
        SIGNUP_URL,
        {'csrfmiddlewaretoken': _csrf(client), 'email': 'noname@example.com', 'password': 'Str0ngPass!23'},
    )
    # 폼을 다시 그리며 에러 표시; 계정은 만들어지지 않는다.
    assert response.status_code == 200
    assert not User.objects.filter(email='noname@example.com').exists()


@pytest.mark.django_db
def test_signup_rejects_too_short_name():
    client = Client()
    response = client.post(
        SIGNUP_URL,
        {
            'csrfmiddlewaretoken': _csrf(client),
            'email': 'short@example.com',
            'name': ' 김 ',  # 공백 제거 후 1자
            'password': 'Str0ngPass!23',
        },
    )
    assert response.status_code == 200
    assert not User.objects.filter(email='short@example.com').exists()


@pytest.mark.django_db
def test_signup_trims_name():
    client = Client()
    client.post(
        SIGNUP_URL,
        {
            'csrfmiddlewaretoken': _csrf(client),
            'email': 'trim@example.com',
            'name': '  이순신  ',
            'password': 'Str0ngPass!23',
        },
    )
    assert User.objects.get(email='trim@example.com').first_name == '이순신'


@pytest.mark.django_db
def test_compensation_label_uses_real_name():
    """정산 화면은 본명으로 사람을 구분한다 (이름 없으면 이메일로 폴백)."""
    from compensation.services import _user_label

    named = User.objects.create_user('named@example.com', 'x', first_name='홍길동')
    unnamed = User.objects.create_user('unnamed@example.com', 'x')
    assert _user_label(named) == '홍길동'
    assert _user_label(unnamed) == 'unnamed@example.com'


@pytest.mark.django_db
def test_signup_page_renders_name_field_and_hint():
    body = Client().get(SIGNUP_URL).content.decode()
    assert 'name="name"' in body
    assert '본명으로 입력해 주세요' in body


@pytest.mark.django_db
def test_invite_signup_also_stores_name():
    """팀원이 들어오는 실제 경로 — 초대 링크 가입도 같은 폼을 쓰므로 이름이 필수/저장된다."""
    from organizations.models import Invitation, Organization

    owner = User.objects.create_user('owner@example.com', 'x')
    org = Organization.create_organization(created_by=owner, title='org')
    invite = Invitation.objects.create(organization=org, created_by=owner, email='mate@example.com')

    client = Client()
    url = f'{SIGNUP_URL}?invite={invite.token}'
    page = client.get(url)
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode()).group(1)

    # 이름 없이 → 거부
    client.post(url, {'csrfmiddlewaretoken': token, 'email': 'mate@example.com', 'password': 'Str0ngPass!23'})
    assert not User.objects.filter(email='mate@example.com').exists()

    # 이름 포함 → 저장
    client.post(
        url,
        {
            'csrfmiddlewaretoken': token,
            'email': 'mate@example.com',
            'name': '정진기',
            'password': 'Str0ngPass!23',
        },
    )
    mate = User.objects.get(email='mate@example.com')
    assert mate.first_name == '정진기'
    assert mate.get_full_name() == '정진기'
