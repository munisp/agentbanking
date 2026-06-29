# Assets Guide

## Directory Structure

```
assets/
├── images/          # App images and illustrations
│   ├── logo.png
│   ├── splash.png
│   └── onboarding/
├── icons/           # Custom icons
│   ├── icon.png
│   ├── adaptive-icon.png
│   └── favicon.png
└── fonts/           # Custom fonts (if any)
```

## Required Assets

### App Icon

- `icon.png` - 1024x1024px, PNG format
- Used for app stores and home screen

### Adaptive Icon (Android)

- `adaptive-icon.png` - 1024x1024px, PNG format
- Foreground icon with transparent background

### Splash Screen

- `splash.png` - 1284x2778px (iPhone 14 Pro Max)
- Background color: #ffffff (configurable in app.json)

### Favicon (Web)

- `favicon.png` - 48x48px or 32x32px, PNG format

## Adding Custom Images

1. Place images in `assets/images/`
2. Import in component:
   ```javascript
   import logo from "../../assets/images/logo.png";
   <Image source={logo} />;
   ```

## Icon Usage

The app uses `react-native-vector-icons` with Material Community Icons.

Browse icons: https://materialdesignicons.com/

Usage:

```javascript
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
<Icon name="home" size={24} color="#000" />;
```

## Optimization

- Use WebP for better compression on Android
- Compress images before adding to project
- Use appropriate resolutions for different screen densities
- Consider using SVG for scalable graphics

## Tools

- Image compression: TinyPNG, ImageOptim
- Icon generation: https://icon.kitchen/
- Asset management: React Native Asset
