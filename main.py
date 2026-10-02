import matplotlib.pyplot as plt
from PIL import Image
import numpy as np

arr = np.array(Image.open("test.jpg").convert("RGB"))

fig, ax = plt.subplots()
ax.imshow(arr)
ax.set_title("点击图片选择要替换的颜色")

def onclick(event):
    if event.xdata is None:
        return
    x, y = int(event.xdata), int(event.ydata)
    print(f"坐标=({x},{y})  RGB={tuple(arr[y, x])}")

fig.canvas.mpl_connect("button_press_event", onclick)
plt.show()