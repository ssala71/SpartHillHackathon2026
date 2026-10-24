// Waypoint look on top of Cloudscape: white surfaces, dark blue accents, Public Sans.
import { applyTheme } from '@cloudscape-design/components/theming'
import { applyMode, Mode } from '@cloudscape-design/global-styles'
import '@fontsource-variable/public-sans'

const brand = { light: '#1f3b73', dark: '#8fb3ff' }
const brandHover = { light: '#162d5a', dark: '#b3ccff' }
const brandActive = { light: '#10224a', dark: '#d2e0ff' }
const onBrand = { light: '#ffffff', dark: '#0b1730' }

const FONT = "'Public Sans Variable', 'Helvetica Neue', Arial, sans-serif"

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
    },
    contexts: {
      'top-navigation': {
        tokens: {
          colorBackgroundContainerContent: '#0b1f3a',
          colorTextAccent: '#8fb3ff',
        },
      },
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
  document.documentElement.dataset.mode = mode
  if (!persist) return
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    // not persisted; the toggle still works for this visit
  }
}

setMode(getMode(), false)
