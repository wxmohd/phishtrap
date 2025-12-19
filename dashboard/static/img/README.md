# PhishTrap Assets

## Required GIF Files (Optional - CSS fallbacks included)

### 1. `phishtrap-bg.gif` - Login Background
- **Size:** < 500KB (optimized)
- **Dimensions:** 1920x1080 or 1600x900
- **Content:** Soft moving particles / flowing lines in purple/blue
- **Style:** Dark, subtle, not too bright
- **Loop:** Seamless infinite loop
- **Recommended tools:** 
  - https://www.vecteezy.com (search "particle background loop")
  - https://ezgif.com/optimize (to compress)

### 2. `loop-orbit.gif` - Dashboard Header Decoration
- **Size:** < 100KB
- **Dimensions:** 200x200px
- **Content:** Spinning holographic ring or orbital network
- **Style:** Transparent background, subtle glow
- **Loop:** Seamless
- **Note:** This is optional - header looks good without it

## CSS Fallback
If GIFs are not added, the design uses CSS gradients and animations as fallback.
The site will still look amazing!

## How to Add GIFs

1. Download optimized GIF files
2. Place them in this directory (`dashboard/static/img/`)
3. Refresh the page - they'll load automatically

## Optimization Tips

```bash
# Use ezgif.com or ImageMagick to optimize:
convert input.gif -fuzz 10% -layers Optimize output.gif
```

Keep file sizes small for fast loading!
