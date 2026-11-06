import typescriptEslint from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import pluginSecurity from "eslint-plugin-security";

export default [
    pluginSecurity.configs.recommended,
    {
      files: ["**/*.ts"],
      plugins: {
        "@typescript-eslint": typescriptEslint,
      },

      languageOptions: {
        parser: tsParser,
        ecmaVersion: 2022,
        sourceType: "module",
      },

      rules: {
        "@typescript-eslint/naming-convention": ["warn", {
            selector: "import",
            format: ["camelCase", "PascalCase"],
        }],

        curly: "warn",
        eqeqeq: "warn",
        "no-throw-literal": "warn",
        semi: "warn",
      },
}];