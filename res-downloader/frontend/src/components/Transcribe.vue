<template>
  <NModal
      :show="showModal"
      :on-update:show="changeShow"
      style="--wails-draggable:no-drag"
      preset="card"
      class="w-[480px]"
      :title="t('index.transcribe')"
  >
    <NForm
        size="medium"
        label-placement="left"
        label-width="auto"
        style="--wails-draggable:no-drag"
    >
      <NFormItem :label="t('index.transcribe_format')">
        <NRadioGroup v-model:value="format">
          <NRadioButton value="srt" label="SRT"/>
          <NRadioButton value="txt" label="TXT"/>
          <NRadioButton value="both" :label="t('index.transcribe_both')"/>
        </NRadioGroup>
      </NFormItem>
      <NFormItem :label="t('index.transcribe_language')">
        <NSelect v-model:value="language" :options="langOptions" style="width: 200px"/>
      </NFormItem>
      <div class="text-xs text-gray-400 mb-3 leading-5">
        {{ t('index.transcribe_tip') }}
      </div>
      <NFormItem>
        <NButton strong secondary type="success" @click="submit" class="w-24">
          {{ t('index.transcribe_start') }}
        </NButton>
      </NFormItem>
    </NForm>
  </NModal>
</template>
<script setup lang="ts">
import {ref, watch} from "vue"
import {useI18n} from 'vue-i18n'
import {useIndexStore} from "@/stores"

const {t} = useI18n()
const store = useIndexStore()

const props = defineProps<{
  showModal: boolean
}>()
const emits = defineEmits(["update:showModal", "submit"])
const changeShow = (value: boolean) => emits("update:showModal", value)

const format = ref(store.globalConfig.SubtitleFormat || "srt")
const language = ref(store.globalConfig.SubtitleLanguage || "zh")

// 打开时同步默认配置
watch(() => props.showModal, (n) => {
  if (n) {
    format.value = store.globalConfig.SubtitleFormat || "srt"
    language.value = store.globalConfig.SubtitleLanguage || "zh"
  }
})

const langOptions = [
  {label: t('index.transcribe_auto'), value: "auto"},
  {label: "中文 (zh)", value: "zh"},
  {label: "English (en)", value: "en"},
  {label: "日本語 (ja)", value: "ja"},
  {label: "한국어 (ko)", value: "ko"},
]

const submit = () => {
  emits("submit", {format: format.value, language: language.value})
}
</script>
