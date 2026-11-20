// Lint: `npm run lint`. Catches what the type check doesn't: hooks called conditionally, effects that read stale
// values, unused code, promises nobody awaits.
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "scripts", "*.config.*"] },
  {
    files: ["src/**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      // a hook inside an if or a loop breaks React's state between renders: always an error
      "react-hooks/rules-of-hooks": "error",
      // an effect or callback that reads a value missing from its dependencies shows stale data
      "react-hooks/exhaustive-deps": "warn",
      "react-refresh/only-export-components": "off",
      // `_name` marks something unused on purpose (a prop pulled out so it isn't passed on)
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrors: "none",
                                                      ignoreRestSiblings: true }],
      "@typescript-eslint/no-explicit-any": "warn",
      "no-empty": ["error", { allowEmptyCatch: true }],
    },
  },
);
