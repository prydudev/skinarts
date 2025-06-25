from time import sleep
from requests import post, get
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from PIL import Image
from rich.console import Console
from rich.style import Style
from rich.theme import Theme
from threading import Thread
from hashlib import md5
import os

theme = Theme({'info': Style(color="#e8eaed", bgcolor="#3b3b3b"), 'error': Style(color="#ff1c1c", bgcolor="#3d0808"), 'success': Style(color="#1bff7a", bgcolor="#0a381d"), 'neutral': Style(color="#ffdb3b", bgcolor="#3d3a2a")})
console = Console(theme=theme)

def gen():
    try:
        image = Image.open("input/image.png").convert("RGBA")
    except FileNotFoundError:
        console.print(f"[error]✗ input/image.png not found.[/error]")
        return

    if image.size != (72, 24):
        console.print(f"[error]✗ image.png must be 72x24 pixels![/error]")
        return

    os.makedirs("skins", exist_ok=True)
    output = []
    hashes = set()

    for row in range(2, -1, -1):
        y_start = row * 8
        for col in range(8, -1, -1):
            x_start = col * 8
            crop_box = (x_start, y_start, x_start + 8, y_start + 8)
            output.append(image.crop(crop_box))

    for i, splice in enumerate(output, start=1):
        try:
            base_skin = Image.open("input/base.png").convert("RGBA")
            base_skin.paste(splice, (8, 8, 16, 16), splice)
            skin_bytes = base_skin.tobytes()
            skin_hash = md5(skin_bytes).hexdigest()
            if skin_hash in hashes:
                px = base_skin.load()
                px[8, 0] = (5, 5, 5, 255)
                skin_bytes = base_skin.tobytes()
                skin_hash = md5(skin_bytes).hexdigest()
            hashes.add(skin_hash)
            base_skin.save(f"skins/{i}.png")
        except FileNotFoundError:
            console.print(f"[error]✗ input/base.png not found.[/error]")
            return
    console.print(f"[success]✓ All skins generated successfully[/success]")


def change_skin(skin_name, bearer, max_retries=5, delay=5):
    file_path = f"skins/{skin_name}.png"
    headers = {"Authorization": f"Bearer {bearer}"}

    try:
        with open(file_path, "rb") as skin_file:
            files = {
                "variant": (None, "slim"),
                "file": (f"{skin_name}.png", skin_file),
            }

            for attempt in range(1, max_retries + 1):
                response = post(
                    url="https://api.minecraftservices.com/minecraft/profile/skins",
                    headers=headers,
                    files=files,
                )
                if response.status_code == 200:
                    return True
                if attempt < max_retries:
                    console.print(f"[error]✗ Attempt {attempt} failed. Retrying in {delay} seconds.[/error]")
                    sleep(delay)
    except FileNotFoundError:
        console.print(f"[error]✗ Skin file not found at {file_path}[/error]")
        return False
    return False

def username(bearer):
    headers = {"Authorization": "Bearer " + bearer}
    response = get("https://api.minecraftservices.com/minecraft/profile", headers=headers)
    if response.status_code == 200:
        return response.json().get("name")
    else:
        console.print(f"[error]✗ Error retrieving username. Please check your Bearer token.[/error]")
        return None

def cache(driver, expected_skin_count):
    while True:
        try:
            driver.refresh()
            wait = WebDriverWait(driver, 15)
            skin_count_element = wait.until(
                EC.presence_of_element_located((By.XPATH, "//strong[contains(., 'Skins')]/a[1]"))
            )
            skin_count = int(skin_count_element.text)

            if skin_count == expected_skin_count:
                return
        except Exception as e:
            console.print(f"[error]✗ An error occurred while caching: {e}. Retrying..[/error]")
        sleep(15)

def applier():
    try:
        with open("input/bearer.txt", "r") as f:
            bearer = f.read().strip()
    except FileNotFoundError:
        console.print(f"[error]✗ input/bearer.txt not found.[/error]")
        return
    ign = username(bearer)
    if not ign:
        return
    confirm = console.input(f"\n[neutral]Are you sure you want to continue as {ign}? (y/n)[/neutral]\n\n[info]→[/info] ")
    if confirm.lower() != 'y':
        return
    skin_files = [f for f in os.listdir("skins") if f.endswith('.png')]
    num_skins_to_apply = len(skin_files)
    applied = 0
    cached = 0
    running = [True]
    def stats():
        while running[0]:
            left = num_skins_to_apply - applied
            console.clear()
            console.print(f"[info]{ign}[/info]\n\n[success]Skins Applied:[/success] [info]{applied}[/info]\n[neutral]Skins Cached:[/neutral] [info]{cached}[/info]\n[error]Skins Left:[/error] [info]{left}[/info]")
            console.print(f"\n[error]Do not close the browser or the program will stop.[/error]\n[neutral]You are free to do other things on your computer while you wait.[/neutral]")
            sleep(5)
    t = Thread(target=stats)
    driver = None
    try:
        driver = uc.Chrome()
        driver.get(f"https://namemc.com/profile/{ign}")
        console.input("[neutral]Please solve Cloudflare challenges and press Enter to continue..[/neutral]")
        try:
            initial_skin_count = int(WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//strong[contains(., 'Skins')]/a[1]"))).text)
        except (TimeoutException, NoSuchElementException):
            initial_skin_count = 1
        t.start()
        for i in range(1, num_skins_to_apply + 1):
            success = change_skin(str(i), bearer)
            if success:
                applied += 1
                expected_skin_count = initial_skin_count + i
                cache(driver, expected_skin_count)
                cached += 1
            else:
                console.print(f"[error]✗ Failed to apply skin {i}. Stopping.[/error]")
                break
        console.clear()
        console.print(f"[success]✓ All skins applied and cached. Exiting.[/success]")
    except Exception as e:
        console.print(f"[error]✗ An unexpected error occurred: {e}[/error]")
    finally:
        running[0] = False
        t.join()
        if driver:
            driver.quit()

def main():
    while True:
        console.print(f"\n[success]1[/success] Apply Skins")
        console.print(f"[neutral]2[/neutral] Generate Skins")
        console.print(f"[error]b[/error] Back")
        choice = console.input(f"\n[info]→[/info] ")

        if choice == '1':
            applier()
        elif choice == '2':
            gen()
        elif choice == 'b':
            break
        else:
            console.print(f"[error]✗ Invalid choice. Please enter 1, 2, or b.[/error]")

main()