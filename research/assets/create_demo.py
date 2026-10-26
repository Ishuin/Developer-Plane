import os
import sys
from PIL import Image, ImageDraw, ImageFont

# Screenshot paths
screenshots = [
    ("01_dashboard.png", "Developer Control Plane\nLive dashboard with 218 projects"),
    ("02_scanning.png", "Scanning your projects\nDiscover repos across any folder"),
    ("03_devto_editor.png", "Publishing content\nLaunch posts created and published"),
    ("04_reddit_form.png", "Community launch\nSharing on Reddit, HN, Twitter, Dev.to"),
]

demo_dir = r"D:\Projects\developer_plane\research\assets\demo"
frames_dir = os.path.join(demo_dir, "frames")
os.makedirs(frames_dir, exist_ok=True)

# Load font
try:
    font = ImageFont.truetype("arial.ttf", 48)
    small_font = ImageFont.truetype("arial.ttf", 32)
except:
    font = ImageFont.load_default()
    small_font = ImageFont.load_default()

frame_duration = 3  # seconds per frame
fps = 30
total_frames = frame_duration * fps

for idx, (screenshot, text) in enumerate(screenshots):
    img_path = os.path.join(demo_dir, screenshot)
    if not os.path.exists(img_path):
        print(f"Missing: {img_path}")
        continue

    img = Image.open(img_path)
    w, h = img.size

    # Create annotated frame
    frame = Image.new("RGB", (w, h), (0, 0, 0))
    frame.paste(img, (0, 0))

    draw = ImageDraw.Draw(frame)

    # Add gradient overlay at bottom
    overlay_height = int(h * 0.25)
    for y in range(h - overlay_height, h):
        alpha = int(255 * (y - (h - overlay_height)) / overlay_height)
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

    # Add text
    lines = text.split("\n")
    y_pos = h - overlay_height + 40
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x_pos = (w - text_width) // 2
        draw.text((x_pos, y_pos), line, fill=(255, 255, 255), font=font)
        y_pos += 60

    # Save frame
    frame_path = os.path.join(frames_dir, f"frame_{idx:03d}.png")
    frame.save(frame_path, "PNG")
    print(f"Created frame {idx+1}/{len(screenshots)}: {frame_path}")

# Create video from frames using FFmpeg
output_video = os.path.join(demo_dir, "developer_plane_demo.mp4")
ffmpeg_cmd = (
    f"ffmpeg -y -framerate {fps} -i {frames_dir}/frame_%03d.png "
    f"-c:v libx264 -pix_fmt yuv420p -crf 23 "
    f"-vf scale=1280:-2 {output_video}"
)
print(f"\nCreating video: {output_video}")
os.system(ffmpeg_cmd)

# Create GIF for README
output_gif = os.path.join(demo_dir, "demo.gif")
gif_cmd = (
    f"ffmpeg -y -framerate {fps//2} -i {frames_dir}/frame_%03d.png "
    f"-vf scale=640:-2,fps=10,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse "
    f"{output_gif}"
)
print(f"Creating GIF: {output_gif}")
os.system(gif_cmd)

print("\nDone!")
print(f"Video: {output_video}")
print(f"GIF: {output_gif}")
