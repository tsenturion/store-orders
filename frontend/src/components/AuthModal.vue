<script setup>
import { ref, reactive, watch, nextTick } from 'vue';
import { X, ArrowRight } from '@lucide/vue';
import { api, user, csrf, notify } from '../store';
const props = defineProps({ open: Boolean });
const emit = defineEmits(['close', 'signed']);
const dialog = ref(null);
const register = ref(false);
const busy = ref(false);
const error = ref('');
const form = reactive({ email: '', password: '', name: '' });
watch(
  () => props.open,
  async (value) => {
    await nextTick();
    if (value) {
      error.value = '';
      dialog.value?.showModal();
    } else dialog.value?.close();
  },
);
async function submit() {
  busy.value = true;
  error.value = '';
  try {
    const data = await api(`/api/auth/${register.value ? 'register' : 'login'}`, {
      method: 'POST',
      body: JSON.stringify(register.value ? form : { email: form.email, password: form.password }),
    });
    user.value = data.user;
    csrf.value = data.csrf;
    form.password = '';
    emit('signed');
    emit('close');
    notify(`Добро пожаловать, ${data.user.name.split(' ')[0]}`);
  } catch (err) {
    error.value = err.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <dialog
    ref="dialog"
    class="m-auto w-[min(440px,92vw)] rounded-2xl border-0 p-8 shadow-2xl backdrop:bg-ink/40"
    aria-labelledby="auth-title"
    @cancel.prevent="emit('close')"
  >
    <button class="absolute right-5 top-5 text-muted" aria-label="Закрыть вход" @click="emit('close')">
      <X :size="20" />
    </button>
    <div class="eyebrow text-accent">Ваш аккаунт</div>
    <h2 id="auth-title" class="mt-3 font-display text-3xl">
      {{ register ? 'Рады знакомству' : 'С возвращением' }}
    </h2>
    <p class="mt-2 text-sm leading-6 text-muted">
      {{
        register
          ? 'Создайте аккаунт, чтобы оформлять заказы и следить за доставкой.'
          : 'Войдите, чтобы продолжить покупки или открыть рабочий кабинет.'
      }}
    </p>
    <form class="mt-6 space-y-4" @submit.prevent="submit">
      <label v-if="register">
        Имя
        <input v-model="form.name" autocomplete="name" required minlength="2" maxlength="100" />
      </label>
      <label>
        Электронная почта
        <input
          v-model="form.email"
          type="email"
          autocomplete="username"
          required
          maxlength="254"
          placeholder="you@example.com"
        />
      </label>
      <label>
        Пароль
        <input
          v-model="form.password"
          type="password"
          :autocomplete="register ? 'new-password' : 'current-password'"
          required
          minlength="8"
          maxlength="128"
        />
      </label>
      <p v-if="error" role="alert" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</p>
      <button class="primary w-full" :disabled="busy">
        {{ busy ? 'Подождите…' : register ? 'Создать аккаунт' : 'Войти' }}
        <ArrowRight :size="16" />
      </button>
    </form>
    <button
      class="mt-5 w-full text-sm text-accent"
      @click="
        register = !register;
        error = '';
      "
    >
      {{ register ? 'Уже есть аккаунт? Войти' : 'Первый раз здесь? Создать аккаунт' }}
    </button>
  </dialog>
</template>
