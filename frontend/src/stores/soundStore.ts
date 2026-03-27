import { create } from 'zustand'
import { Howl } from 'howler'

type SoundKey =
  | 'card_deal'
  | 'community_card'
  | 'check'
  | 'chip_bet'
  | 'pot_collected_small'
  | 'pot_collected_large'
  | 'your_turn'
  | 'fold'
  | 'all_in'
  | 'vote_banner'

// Placeholder paths — drop real .mp3 files in public/sounds/ to activate
const SOUND_PATHS: Record<SoundKey, string> = {
  card_deal: '/sounds/card_deal.mp3',
  community_card: '/sounds/community_card.mp3',
  check: '/sounds/check_knock.mp3',
  chip_bet: '/sounds/chip_bet.mp3',
  pot_collected_small: '/sounds/pot_small.mp3',
  pot_collected_large: '/sounds/pot_large.mp3',
  your_turn: '/sounds/your_turn.mp3',
  fold: '/sounds/fold.mp3',
  all_in: '/sounds/all_in.mp3',
  vote_banner: '/sounds/vote_banner.mp3',
}

interface SoundState {
  muted: boolean
  sounds: Partial<Record<SoundKey, Howl>>
  loaded: boolean

  load: () => void
  play: (key: SoundKey) => void
  toggleMute: () => void
}

export const useSoundStore = create<SoundState>((set, get) => ({
  muted: false,
  sounds: {},
  loaded: false,

  load: () => {
    if (get().loaded) return
    const sounds: Partial<Record<SoundKey, Howl>> = {}
    for (const [key, src] of Object.entries(SOUND_PATHS) as [SoundKey, string][]) {
      sounds[key] = new Howl({
        src: [src],
        preload: true,
        volume: 0.6,
        onloaderror: () => {
          // Silently ignore missing audio files — placeholders
        },
      })
    }
    set({ sounds, loaded: true })
  },

  play: (key: SoundKey) => {
    const { muted, sounds } = get()
    if (muted) return
    const howl = sounds[key]
    if (howl) {
      try {
        howl.play()
      } catch {
        // Ignore autoplay errors
      }
    }
  },

  toggleMute: () => {
    const muted = !get().muted
    set({ muted })
    // Also mute/unmute all Howl instances
    const { sounds } = get()
    for (const howl of Object.values(sounds)) {
      howl?.mute(muted)
    }
  },
}))
