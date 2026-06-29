module.exports = {
  root: true,
  extends: ["@react-native"],
  parser: "@babel/eslint-parser",
  parserOptions: {
    requireConfigFile: false,
    ecmaVersion: 2021,
    sourceType: "module",
    ecmaFeatures: {
      jsx: true,
    },
  },
  rules: {
    "react/react-in-jsx-scope": "off",
    "react-native/no-inline-styles": "warn",
    "no-console": ["warn", { allow: ["warn", "error"] }],
    "prettier/prettier": "off",
  },
};
