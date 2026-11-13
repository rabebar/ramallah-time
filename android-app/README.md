# مُعين التنفيذي — Android package

This directory contains the Capacitor Android wrapper for the existing Moeen
Executive web app. It keeps the current Flask backend, authentication,
encrypted sync, reminders, audio, and push notification endpoints.

## Build the APK

1. Install Node.js, Java 17, and Android Studio/SDK.
2. The wrapper is configured for `https://rtstudio.store/moeen-executive/`. Change the URL in `capacitor.config.json` only if production moves.

3. Install the wrapper dependencies and create the Android project:

   ```powershell
   npm install
   npx cap add android
   npx cap sync android
   npx cap open android
   ```

4. Build a signed APK from Android Studio. Place the release file at
   `static/downloads/moeen-executive.apk` when it is ready for the RT Studio
   product page.

For a command-line release build, provide the local signing values and run
`assembleRelease` from the `android` directory:

```powershell
$env:ANDROID_HOME = 'C:\Users\user\AppData\Local\Android\Sdk'
$env:MOEEN_KEYSTORE_PATH = (Resolve-Path '..\keystore\moeen-release.jks').Path
$env:MOEEN_KEYSTORE_PASSWORD = 'your-local-keystore-password'
$env:MOEEN_KEY_ALIAS = 'moeen'
$env:MOEEN_KEY_PASSWORD = $env:MOEEN_KEYSTORE_PASSWORD
./gradlew.bat assembleRelease
```

The wrapper requires an HTTPS production URL. The app is online-first because
account data and encrypted synchronization live on the Flask service.
