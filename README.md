# Space Invader – Android build

Project layout: `main.py`, `buildozer.spec`, `assets/`.

## Option A – build on a Linux PC (or WSL / Colab)
    pip install buildozer cython
    buildozer android debug
The APK appears in `bin/`. Copy it to your phone and tap it to install
(allow "install unknown apps" when asked).

## Option B – build in the cloud (no PC needed)
1. Create a free GitHub repo and upload everything in this folder
   (keep the `.github/workflows/build.yml` path).
2. Open the repo's Actions tab -> "Build APK" -> Run workflow.
3. When it finishes, download the `space-invader-apk` artifact and install the APK.

## Controls on Android
< > move, hold FIRE to shoot (hold for the laser), REVIVE appears after game over,
MENU / system Back returns to the menu.

## Desktop testing
    TOUCH_UI=1 python main.py     # shows the on-screen buttons; mouse acts as a finger
