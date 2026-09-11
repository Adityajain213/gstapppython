name: Build Android APK

on:
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-22.04

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "17"

      - name: Setup Android SDK
        uses: android-actions/setup-android@v4
        with:
          packages: ""

      - name: Install Android SDK packages
        run: |
          yes | sdkmanager --licenses >/dev/null 2>&1 || true

          sdkmanager --install \
            "platform-tools" \
            "platforms;android-35" \
            "build-tools;35.0.0" \
            "cmdline-tools;latest"
          
          # Verify AIDL is available
          ls -la "$ANDROID_SDK_ROOT/build-tools/35.0.0/"

      - name: Install system dependencies
        run: |
          sudo apt-get update

          sudo apt-get install -y \
            git \
            zip \
            unzip \
            autoconf \
            automake \
            libtool \
            pkg-config \
            zlib1g-dev \
            libncurses5-dev \
            libncursesw5-dev \
            cmake \
            libffi-dev \
            libssl-dev \
            libltdl-dev

      - name: Install Buildozer
        run: |
          python -m pip install --upgrade pip
          python -m pip install buildozer cython==0.29.34

      - name: Prepare Buildozer SDK
        run: |
          SDK="$ANDROID_SDK_ROOT"

          echo "Real Android SDK:"
          echo "$SDK"

          echo "SDK contents:"
          ls -la "$SDK"

          mkdir -p "$HOME/.buildozer/android/platform"

          rm -rf "$HOME/.buildozer/android/platform/android-sdk"

          cp -a "$SDK" "$HOME/.buildozer/android/platform/android-sdk"

          echo "Buildozer SDK:"
          ls -la "$HOME/.buildozer/android/platform/android-sdk"

          echo "Build Tools:"
          ls -la "$HOME/.buildozer/android/platform/android-sdk/build-tools"

          # Create tools/bin symlink for sdkmanager
          mkdir -p "$HOME/.buildozer/android/platform/android-sdk/tools/bin"
          ln -sf "$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager" \
            "$HOME/.buildozer/android/platform/android-sdk/tools/bin/sdkmanager"
          
          ln -sf "$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/avdmanager" \
            "$HOME/.buildozer/android/platform/android-sdk/tools/bin/avdmanager"

          echo "AIDL:"
          ls -la "$HOME/.buildozer/android/platform/android-sdk/build-tools/35.0.0/aidl"

      - name: Build APK
        env:
          BUILDOZER_WARN_ON_ROOT: "0"
          PYTHONFORANDROID_PREREQUISITES_INSTALL_INTERACTIVE: "0"
        run: |
          buildozer -v android debug

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: InvoiceExtractor-APK
          path: bin/*.apk
          if-no-files-found: error
