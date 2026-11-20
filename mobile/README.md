# Focs for Android

The Android app. It is a thin native shell (Capacitor) around the web app: the app carries one screen of its own,
which learns where your Focs server is, and from then on it shows that server's own pages. The account, plan,
notes, tests and everything else are the same ones as on the web, and the app is never a version behind it.

```
mobile/
  build_apk.bat          builds the APK            ->  Focs-debug.apk  (or Focs.apk with "release")
  serve_for_phone.bat    starts Focs so a phone on the same Wi-Fi can reach it
  server.txt             the server the app opens on first launch (optional)
  capacitor.config.json  app id, name, colours
  android/               the Android project (icon, launch screen, permissions, back button)
  www/                   the app's own screen, built from ../frontend (not in git)
```

## Build it

```
mobile\build_apk.bat
```

The first run downloads Gradle and takes several minutes; later runs take about one. The result is
`mobile\Focs-debug.apk`. Copy it to a phone and open it (Android asks once to allow installing from that app), or
with USB debugging on: `adb install -r Focs-debug.apk`.

It needs three things on the computer, found automatically in these places:

| | Where the script looks | Getting it |
| --- | --- | --- |
| Node.js 20+ | `PATH` | already needed for the web app |
| A Java 21 JDK | `JAVA_HOME`, else `%USERPROFILE%\.jdks\jdk-21*` | unzip [Temurin 21](https://adoptium.net/temurin/releases/?version=21&os=windows) into `%USERPROFILE%\.jdks` |
| The Android SDK | `ANDROID_HOME`, else `%LOCALAPPDATA%\Android\Sdk` | Android Studio installs it there; or the commands below |

Without Android Studio: unzip Google's [command-line tools](https://developer.android.com/studio#command-line-tools-only)
so that `%LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest\bin\sdkmanager.bat` exists, then

```
set JAVA_HOME=%USERPROFILE%\.jdks\jdk-21...
cd %LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest\bin
sdkmanager --licenses
sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0" "build-tools;34.0.0"
```

Build files are written to `%LOCALAPPDATA%\FocsAndroidBuild`, not into this folder: the project sits in OneDrive,
which locks files that change as fast as a build's do.

## Connect it to a server

The app needs a Focs server it can reach.

- **Focs on the internet** (the real set-up): put its address in `server.txt` (`https://focs.example.com`) and build.
  The app opens it directly.
- **Focs on this computer, phone on the same Wi-Fi** (for trying it out): start Focs with `mobile\serve_for_phone.bat`
  instead of `run.bat`. It prints a line like `On your phone : http://192.168.1.5:8000`. Type that into the app.
  Windows may ask once to let Python through the firewall on private networks: say yes. While Focs runs this way,
  anyone on the same network can open it, so use it at home, not on a public Wi-Fi.

With no `server.txt` the app asks for the address the first time it is opened. It can be changed later from
Settings, Server, and the app comes back to its own screen whenever the server doesn't answer.

## What is different in the app

- Sharing a browser tab for a live lecture is a desktop feature; in the app use **Board photo** and **Ask with a photo**.
- A file shared on Campus is read inside the app, page by page.
- Saving a file (your data, a lecture's notes) and printing are not in the app yet: it says so and points to the browser.
- The microphone (spoken answers) needs an `https://` server; over plain `http://` on Wi-Fi Android does not allow it.

## Before publishing

- **App id**: `com.focs.app` in `capacitor.config.json` and `android/app/build.gradle`. It can never change once the
  app is on the Play Store, so set the one you want first (the Java package folder follows it).
- **Signing**: a debug APK is fine for your own phones. For anything you hand out, make a key once and build a
  release: see `keystore.properties.example`, then `build_apk.bat release` writes `Focs.apk`. Keep the key safe:
  an update must be signed with the same one.
- **Version**: `versionCode` (a number that goes up with every upload) and `versionName` in `android/app/build.gradle`.
- The Play Store wants an `.aab`: `gradlew bundleRelease` in `android/` makes one with the same key.
