export default [
  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        "console": "readonly",
        "document": "readonly",
        "window": "readonly",
        "fetch": "readonly",
        "WebSocket": "readonly",
        "setTimeout": "readonly",
        "setInterval": "readonly",
        "clearTimeout": "readonly",
        "clearInterval": "readonly",
        "alert": "readonly",
        "confirm": "readonly",
        "URL": "readonly",
        "Blob": "readonly",
        "getComputedStyle": "readonly",
        "FormData": "readonly",
        "FileReader": "readonly"
      }
    },
    rules: {
      "no-unused-vars": "warn",
      "no-undef": "error",
      "no-console": "off",
      "semi": ["error", "always"],
      "quotes": ["warn", "single"],
      "no-unreachable": "error",
      "no-duplicate-case": "error",
      "no-empty": "warn"
    }
  }
];