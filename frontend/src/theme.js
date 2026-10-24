// Waypoint look on top of Cloudscape: white surfaces, dark blue accents, Inter.
import { applyTheme } from '@cloudscape-design/components/theming'
import { applyMode, Mode } from '@cloudscape-design/global-styles'
import '@fontsource-variable/inter'

const brand = { light: '#1f3b73', dark: '#8fb3ff' }
const brandHover = { light: '#162d5a', dark: '#b3ccff' }
const brandActive = { light: '#10224a', dark: '#d2e0ff' }
const onBrand = { light: '#ffffff', dark: '#0b1730' }

// Bundled so the demo and admin look the same on Mac, Windows, and Linux.
const FONT = "'Inter Variable', ui-sans-serif, -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

applyTheme({
  theme: {
    tokens: {
      fontFamilyBase: FONT,
      colorBackgroundButtonPrimaryDefault: brand,
      colorBackgroundButtonPrimaryHover: brandHover,
      colorBackgroundButtonPrimaryActive: brandActive,
      colorTextButtonPrimaryDefault: onBrand,
      colorTextButtonPrimaryHover: onBrand,
      colorTextButtonPrimaryActive: onBrand,
      colorBorderButtonNormalDefault: brand,
      colorBorderButtonNormalHover: brandHover,
      colorBorderButtonNormalActive: brandActive,
      colorTextButtonNormalDefault: brand,
      colorTextButtonNormalHover: brandHover,
      colorTextButtonNormalActive: brandActive,
      colorBackgroundButtonNormalHover: { light: '#eef3fb', dark: '#13233f' },
      colorBackgroundButtonNormalActive: { light: '#dce6f7', dark: '#1a2f52' },
      colorTextLinkDefault: brand,
      colorTextLinkHover: brandHover,
      colorTextAccent: brand,
      colorTextInteractiveActive: brand,
      colorBorderItemFocused: brand,
      colorBorderItemSelected: brand,
      colorBackgroundItemSelected: { light: '#eef3fb', dark: '#13233f' },
      colorBackgroundDropdownItemSelected: { light: '#eef3fb', dark: '#13233f' },
      colorBackgroundControlChecked: brand,
      colorBackgroundSegmentActive: brand,
      colorTextSegmentActive: onBrand,
      colorBackgroundProgressBarValueDefault: brand,
      colorBackgroundLayoutToggleActive: brand,
      // Navy surfaces in dark mode, matching the top bar and the public demo.
      colorBackgroundLayoutMain: { light: '#ffffff', dark: '#0b1220' },
      colorBackgroundLayoutPanelContent: { light: '#ffffff', dark: '#0b1220' },
      colorBackgroundContainerContent: { light: '#ffffff', dark: '#111a2c' },
      colorBackgroundContainerHeader: { light: '#ffffff', dark: '#111a2c' },
      colorBackgroundInputDefault: { light: '#ffffff', dark: '#0b1220' },
    },
  },
})

const STORAGE_KEY = 'waypoint-mode'

export function getMode() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return saved
  } catch {
    // storage unavailable; fall through to system preference
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function setMode(mode, persist = true) {
  applyMode(mode === 'dark' ? Mode.Dark : Mode.Light)
  document.documentElement.classList.toggle('dark', mode === 'dark')
  if (!persist) return
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    // not persisted; the toggle still works for this visit
  }
}

setMode(getMode(), false)
