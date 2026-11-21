# レンダリングしたスプライトを1枚にまとめる: 行=色1〜5、列=つながり0〜15・16=消える顔
import sys
from PIL import Image
src, out = sys.argv[1], sys.argv[2]
P = 128
im = Image.new("RGBA", (17 * P, 5 * P), (0, 0, 0, 0))
for c in range(1, 6):
    for m in range(17):
        n = f"s{c}_pop.png" if m == 16 else f"s{c}_{m:02d}.png"
        try:
            t = Image.open(f"{src}/{n}").convert("RGBA").resize((P, P), Image.LANCZOS)
        except FileNotFoundError:
            continue
        im.alpha_composite(t, (m * P, (c - 1) * P))
im.save(out, optimize=True)
