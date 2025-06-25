<template>
  <main>
    <LoginForm v-if="!isLoggedIn" @login="handleLogin" />
    <ModelList v-else />
  </main>
</template>

<script setup>
import { ref } from 'vue'
import LoginForm from './components/LoginForm.vue'
import ModelList from './components/ModelList.vue'

const isLoggedIn = ref(false)

function handleLogin(username) {
  console.log('登入成功，使用者：', username)
  isLoggedIn.value = true
}
</script>

<style scoped>
main {
  padding: 2rem;
  font-family: sans-serif;
}
</style>
