"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging

from django import forms
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from users.models import User

EMAIL_MAX_LENGTH = 256
USERNAME_MAX_LENGTH = 30
DISPLAY_NAME_LENGTH = 100
# 회원가입 시 받는 본명. User.first_name 컬럼(max_length=256)에 저장한다.
NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 256
USERNAME_LENGTH_ERR = f'Please enter a username {USERNAME_MAX_LENGTH} characters or fewer in length'
DISPLAY_NAME_LENGTH_ERR = f'Please enter a display name {DISPLAY_NAME_LENGTH} characters or fewer in length'
INVALID_USER_ERROR = "The email and password you entered don't match."

FOUND_US_ELABORATE = 'Other'
# (code, stored value, 화면 표시). 저장 값은 영어 그대로 둔다 — 이 문자열이 그대로
# `how_find_us` 에 저장되고 `FOUND_US_ELABORATE` 비교에도 쓰이므로, 번역하면 기존
# 데이터와 "기타 선택 시 상세 입력" 분기가 함께 깨진다.
FOUND_US_OPTIONS = (
    ('Gi', 'Github', 'GitHub'),
    ('Em', 'Email or newsletter', '이메일 또는 뉴스레터'),
    ('Se', 'Search engine', '검색 엔진'),
    ('Fr', 'Friend or coworker', '지인 또는 동료'),
    ('Ad', 'Ad', '광고'),
    ('Ot', FOUND_US_ELABORATE, '기타'),
)

logger = logging.getLogger(__name__)


class LoginForm(forms.Form):
    """For logging in to the app and all - session based"""

    # use username instead of email when LDAP enabled
    email = forms.CharField(label='User') if settings.USE_USERNAME_FOR_LOGIN else forms.EmailField(label='Email')
    password = forms.CharField(widget=forms.PasswordInput())
    persist_session = forms.BooleanField(widget=forms.CheckboxInput(), required=False)

    def clean(self, *args, **kwargs):
        cleaned = super(LoginForm, self).clean()
        email = cleaned.get('email', '').lower()
        password = cleaned.get('password', '')
        if len(email) >= EMAIL_MAX_LENGTH:
            raise forms.ValidationError('Email is too long')

        # advanced way for user auth
        user = settings.USER_AUTH(User, email, password)

        # regular access
        if user is None:
            user = auth.authenticate(email=email, password=password)

        if user and user.is_active:
            persist_session = cleaned.get('persist_session', False)
            return {'user': user, 'persist_session': persist_session}
        else:
            raise forms.ValidationError(INVALID_USER_ERROR)


class UserSignupForm(forms.Form):
    email = forms.EmailField(label='Work Email', error_messages={'required': 'Invalid email'})
    # 본명. 정산·작업 내역에서 이메일과 함께 사람을 식별하는 안전장치라 필수.
    # `User.first_name` 한 칸에 전체 이름을 넣는다 — `get_full_name()` 이 first+last 를
    # 공백으로 잇기 때문에 한글 이름을 성/이름으로 쪼개면 "홍 길동" 처럼 벌어진다.
    name = forms.CharField(
        max_length=NAME_MAX_LENGTH,
        error_messages={'required': '이름을 입력해 주세요'},
    )
    password = forms.CharField(widget=forms.TextInput(attrs={'type': 'password'}))
    allow_newsletters = forms.BooleanField(required=False)
    how_find_us = forms.CharField(required=False)
    elaborate = forms.CharField(required=False)

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if len(name) < NAME_MIN_LENGTH:
            raise forms.ValidationError(f'이름은 {NAME_MIN_LENGTH}자 이상이어야 합니다')
        return name

    def clean_password(self):
        password = self.cleaned_data.get('password')
        try:
            validate_password(password)
        except DjangoValidationError as e:
            raise forms.ValidationError(e.messages)
        return password

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username=username.lower()).exists():
            raise forms.ValidationError('User with username already exists')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email').lower()
        if len(email) >= EMAIL_MAX_LENGTH:
            raise forms.ValidationError('Email is too long')

        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('User with this email already exists')

        return email

    def save(self):
        cleaned = self.cleaned_data
        password = cleaned['password']
        email = cleaned['email'].lower()
        allow_newsletters = None
        how_find_us = None
        if 'allow_newsletters' in cleaned:
            allow_newsletters = cleaned['allow_newsletters']
        if 'how_find_us' in cleaned:
            how_find_us = cleaned['how_find_us']
        if 'elaborate' in cleaned and how_find_us == FOUND_US_ELABORATE:
            cleaned['elaborate']

        # 이름은 first_name 에만 넣는다. `get_full_name()` 이 first + ' ' + last 라서,
        # 정산·작업 내역·아바타 이니셜이 별도 수정 없이 본명을 그대로 쓴다.
        user = User.objects.create_user(
            email, password, allow_newsletters=allow_newsletters, first_name=cleaned['name']
        )
        return user


class UserProfileForm(forms.ModelForm):
    """This form is used in profile account pages"""

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone', 'allow_newsletters')
