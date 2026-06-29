# Sound Assets for Notifications

This directory contains sound files used for transaction notifications and alerts.

## Required Sound Files

Add the following sound files to this directory:

1. **notification.mp3** - Played when a transaction is received
   - Recommended: Pleasant beep or chime sound
   - Duration: 1-2 seconds
   - Format: MP3

2. **warning.mp3** - Played when a geofence violation occurs
   - Recommended: Alert or warning sound
   - Duration: 1-2 seconds
   - Format: MP3

## Where to Get Sounds

You can:
- Use royalty-free sounds from sites like:
  - https://freesound.org/
  - https://mixkit.co/free-sound-effects/
  - https://www.zapsplat.com/
  
- Create your own using audio editing software
- Use system notification sounds

## Adding Sounds

1. Place the MP3 files in this directory
2. Ensure filenames match exactly: `notification.mp3` and `warning.mp3`
3. Recommended file size: < 100KB each

## Testing

After adding sounds, test them by:
1. Triggering a test transaction
2. Moving outside a geofence boundary

The sounds should play automatically when notifications are received.
