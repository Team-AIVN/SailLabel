"""브랜드 로고 마크(워드마크 제외)를 파비콘 자산으로 래스터라이즈한다.

도형은 ``web/apps/labelstudio/src/assets/images/logo.svg`` 의 <g> 그룹과 동일하다
(그 뒤의 <text> 워드마크는 제외 — 파비콘엔 마크만 들어간다).
로고를 바꾸면 이 좌표도 같이 고치고 아래를 다시 실행할 것.

    poetry run python scripts/make_favicon.py

생성물:
    label_studio/core/static/images/favicon.ico   (Django base.html 이 서빙)
    label_studio/core/static/images/favicon.png
    web/apps/labelstudio/src/favicon.ico          (webpack dev index.html)
"""

import os

from PIL import Image, ImageDraw

ORANGE = (255, 117, 87, 255)  # #FF7557
CREAM = (255, 214, 205, 255)  # #FFD6CD

# logo.svg <g> 안의 도형 bbox + 여백을 정사각으로 맞춘다.
X0, Y0, X1, Y1 = 48, 45, 268, 206
PAD = 12
SIDE = (X1 - X0) + 2 * PAD
OFF_X = PAD
OFF_Y = PAD + ((SIDE - 2 * PAD) - (Y1 - Y0)) / 2

RENDER = 1024  # 슈퍼샘플 후 LANCZOS 축소
SCALE = RENDER / SIDE
ICO_SIZES = [16, 32, 48, 64, 128, 256]

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def px(x, y):
    return ((x - X0 + OFF_X) * SCALE, (y - Y0 + OFF_Y) * SCALE)


def rect(draw, x, y, w, h, fill):
    x0, y0 = px(x, y)
    x1, y1 = px(x + w, y + h)
    draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=fill)


def poly(draw, pts, fill, stroke, width):
    p = [px(*pt) for pt in pts]
    draw.polygon(p, fill=fill)
    draw.line(p + [p[0]], fill=stroke, width=int(round(width * SCALE)), joint='curve')


def render():
    img = Image.new('RGBA', (RENDER, RENDER), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rect(d, 140, 45, 38, 38, ORANGE)  # 돛대 머리
    poly(d, [(160, 72), (122, 122), (198, 122)], CREAM, ORANGE, 11)  # 돛
    poly(d, [(82, 127), (238, 127), (206, 190), (114, 190)], CREAM, ORANGE, 12)  # 선체
    rect(d, 70, 120, 180, 14, ORANGE)  # 갑판
    rect(d, 48, 102, 38, 38, ORANGE)  # 좌상 브래킷
    rect(d, 230, 102, 38, 38, ORANGE)  # 우상 브래킷
    rect(d, 96, 177, 128, 13, ORANGE)  # 용골
    rect(d, 86, 168, 38, 38, ORANGE)  # 좌하 브래킷
    rect(d, 192, 168, 38, 38, ORANGE)  # 우하 브래킷
    return img


def main():
    img = render()
    frames = [img.resize((s, s), Image.LANCZOS) for s in ICO_SIZES]

    targets = [
        os.path.join(HERE, 'label_studio', 'core', 'static', 'images', 'favicon.ico'),
        os.path.join(HERE, 'web', 'apps', 'labelstudio', 'src', 'favicon.ico'),
    ]
    for path in targets:
        frames[-1].save(path, format='ICO', sizes=[(s, s) for s in ICO_SIZES])
        print(f'wrote {path}')

    png = os.path.join(HERE, 'label_studio', 'core', 'static', 'images', 'favicon.png')
    img.resize((256, 256), Image.LANCZOS).save(png)
    print(f'wrote {png}')


if __name__ == '__main__':
    main()
