#!/usr/bin/env python3
"""
夜間 Nocturne Bar - PWA 圖示產生器

用法：
    pip install pillow
    python gen_icons.py

會在本檔案同一層的 icons/ 資料夾輸出：
    icon-{72,96,128,144,152,192,384,512}.png  一般圖示 (purpose: any, 圓角、角落透明)
    maskable-{192,512}.png                     可遮罩圖示 (purpose: maskable, 滿版、內容留在安全區)
    apple-touch-icon.png (180x180)            iOS 主畫面圖示 (滿版、不透明)
    favicon-16.png / favicon-32.png / favicon.ico
"""

from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageOps

# ==================== 設計參數 ====================
# 您可以自由修改下方的顏色數值來改變視覺風格

BG = "#0a0a0c"            # 背景顏色（與 manifest theme_color 一致）
GLOW = (245, 158, 11)     # 背景中心微光（琥珀橘色 RGB）
BRASS_TOP = "#ffdfaa"     # 黃銅漸層：上
BRASS_MID = "#c5a059"     # 黃銅漸層：中
BRASS_BOT = "#8a6a2c"     # 黃銅漸層：下

MASTER = 2048             # 母圖尺寸（超高解析度，縮小後邊緣較平滑）
OUT_DIR = Path(__file__).resolve().parent / "icons"

ANY_SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
MASKABLE_SIZES = [192, 512]

# ==================== 繪圖工具 ====================

def brass_fill(size: int) -> Image.Image:
    """產生由上到下的黃銅漸層背景"""
    grad = Image.linear_gradient("L").resize((size, size), Image.Resampling.BILINEAR)
    # 透過彩色轉移建立上、中、下的金屬漸層
    return ImageOps.colorize(grad, black=BRASS_BOT, mid=BRASS_MID, white=BRASS_TOP)

def glow_layer(size: int, strength: int = 55) -> Image.Image:
    """產生體現深夜氛圍的中央圓形微光"""
    radial = Image.radial_gradient("L").resize((size, size), Image.Resampling.BILINEAR) # 中心黑 -> 邊緣白
    # 反轉放射漸層，使其中心亮、邊緣暗，並加上強度控制
    alpha = ImageOps.invert(radial).point(lambda v: int(v * strength / 255))
    
    layer = Image.new("RGBA", (size, size), GLOW + (0,))
    layer.putalpha(alpha)
    return layer

def n_polygons(cx: float, cy: float, height: float) -> list:
    """計算標誌幾何多邊形的頂點坐標"""
    h = height / 2
    w = height * 0.45       # 半寬
    th = height * 0.052     # 線條粗細
    
    # 根據中心點與尺寸回傳多邊形頂點群
    return [
        (cx - w, cy - h), (cx + w, cy - h), 
        (cx + w, cy - h + th), (cx - w, cy - h + th)
    ]

def rect(x0, y0, x1, y1):
    """輔助建立矩形頂點元組"""
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

# ==================== 核心生成邏輯 ====================

def make_master(maskable: bool = False) -> Image.Image:
    """建立超高解析度的 Master 母圖"""
    # 1. 建立基底背景
    img = Image.new("RGBA", (MASTER, MASTER), BG)
    
    # 2. 疊加中央發光層
    glow = glow_layer(MASTER, strength=60)
    img = Image.alpha_composite(img, glow)
    
    # 3. 建立標誌繪圖遮罩
    mask = Image.new("L", (MASTER, MASTER), 0)
    draw = ImageDraw.Draw(mask)
    
    # 在中央繪製夜間 Bar 的幾何標誌圖案 (N 圖騰)
    cx, cy = MASTER / 2, MASTER / 2
    logo_h = MASTER * 0.45 if maskable else MASTER * 0.55
    
    # 繪製標誌的幾何線條
    poly1 = n_polygons(cx, cy, logo_h)
    draw.polygon(poly1, fill=255)
    
    # 交叉斜線與右側垂直裝飾線
    draw.polygon([(cx - logo_h*0.2, cy - logo_h*0.2), (cx + logo_h*0.2, cy + logo_h*0.2), 
                  (cx + logo_h*0.15, cy + logo_h*0.2), (cx - logo_h*0.25, cy - logo_h*0.2)], fill=255)
    
    # 4. 將黃銅漸層填入標誌遮罩中
    brass = brass_fill(MASTER)
    img.paste(brass, (0, 0), mask=mask)
    
    return img

def save_icon(img: Image.Image, size: int, output_name: str, round_corners: bool = False):
    """將母圖縮放到指定尺寸並儲存"""
    resized = img.resize((size, size), Image.Resampling.LANCZOS)
    
    if round_corners:
        # 為 any 用途的 icon 加上精緻的圓角效果
        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        radius = int(size * 0.18) # 經典的 PWA 圓角比例
        draw.rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
        
        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        output.paste(resized, (0, 0), mask=mask)
        output.save(OUT_DIR / output_name, "PNG")
    else:
        # 滿版輸出（如 maskable 或 apple-touch-icon）
        # 轉為 RGB 確保不帶透明通道，符合 PWA 安全區域與 iOS 規範
        output = resized.convert("RGB")
        output.save(OUT_DIR / output_name, "PNG")

# ==================== 主程式進入點 ====================

def main():
    # 建立輸出資料夾
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"開始產生圖示，輸出目錄：{OUT_DIR}")
    
    # 產生兩種母圖（標準版與專為可遮罩優化的安全區域版）
    master_standard = make_master(maskable=False)
    master_maskable = make_master(maskable=True)
    
    # 1. 產生標準 PWA Any 圖示 (帶圓角)
    for size in ANY_SIZES:
        save_icon(master_standard, size, f"icon-{size}x{size}.png", round_corners=True)
        # 同時產生一份不帶圓角的備用檔
        save_icon(master_standard, size, f"icon-{size}.png", round_corners=False)
        
    # 2. 產生 PWA Maskable 圖示 (滿版安全區)
    for size in MASKABLE_SIZES:
        save_icon(master_maskable, size, f"maskable-{size}.png", round_corners=False)
        
    # 3. 產生 iOS 主畫面圖示 (180x180)
    save_icon(master_standard, 180, "apple-touch-icon.png", round_corners=False)
    
    # 4. 產生網頁 Favicons
    save_icon(master_standard, 16, "favicon-16.png", round_corners=False)
    save_icon(master_standard, 32, "favicon-32.png", round_corners=False)
    
    # 儲存 ico 格式
    ico_img = master_standard.resize((32, 32), Image.Resampling.LANCZOS).convert("RGB")
    ico_img.save(OUT_DIR / "favicon.ico", format="ICO")
    
    print("✨ 所有圖示已順利全數產生完成！")

if __name__ == "__main__":
    main()
