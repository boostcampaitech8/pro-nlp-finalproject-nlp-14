/**
 * 오디오 설정 localStorage 유틸리티
 * 회의 간 사용자 오디오 설정 유지를 위한 저장/로드 함수
 */

// localStorage 키
const AUDIO_SETTINGS_KEY = 'mit-audio-settings';
const REMOTE_VOLUMES_KEY = 'mit-remote-volumes';

// 오디오 설정 타입
export interface AudioSettings {
  micGain: number;
  audioInputDeviceId: string | null;
  audioOutputDeviceId: string | null;
}

/**
 * localStorage에서 오디오 설정 불러오기
 */
export function loadAudioSettings(): Partial<AudioSettings> {
  try {
    const stored = localStorage.getItem(AUDIO_SETTINGS_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    console.warn('[audioSettingsStorage] Failed to load audio settings:', e);
  }
  return {};
}

/**
 * localStorage에 오디오 설정 저장
 */
export function saveAudioSettings(settings: AudioSettings): void {
  try {
    localStorage.setItem(AUDIO_SETTINGS_KEY, JSON.stringify(settings));
  } catch (e) {
    console.warn('[audioSettingsStorage] Failed to save audio settings:', e);
  }
}

/**
 * localStorage에서 참여자별 볼륨 불러오기
 */
export function loadRemoteVolumes(): Map<string, number> {
  try {
    const stored = localStorage.getItem(REMOTE_VOLUMES_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      return new Map(Object.entries(parsed));
    }
  } catch (e) {
    console.warn('[audioSettingsStorage] Failed to load remote volumes:', e);
  }
  return new Map();
}

/**
 * localStorage에 참여자별 볼륨 저장
 */
export function saveRemoteVolumes(volumes: Map<string, number>): void {
  try {
    const obj = Object.fromEntries(volumes);
    localStorage.setItem(REMOTE_VOLUMES_KEY, JSON.stringify(obj));
  } catch (e) {
    console.warn('[audioSettingsStorage] Failed to save remote volumes:', e);
  }
}
