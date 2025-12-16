import siteConfig from '@generated/docusaurus.config';
export default function prismIncludeLanguages(PrismObject) {
  const {
    themeConfig: {prism},
  } = siteConfig;
  const {additionalLanguages} = prism;
  // Prism components work on the Prism instance on the window, while prism-
  // react-renderer uses its own Prism instance. We temporarily mount the
  // instance onto window, import components to enhance it, then remove it to
  // avoid polluting global namespace.
  // You can mutate PrismObject: registering plugins, deleting languages... As
  // long as you don't re-assign it
  const PrismBefore = globalThis.Prism;

  PrismObject.languages.dsl = {
  'comment': {
    pattern: /#.*/,
    greedy: true,
  },
  'header': {
    pattern: /\b(Data|Actions|Events|Mission)(?=:)/m,
    alias: 'keyword',
  },
  'transition': {
    pattern: /\b(Start|During|done)\b/,
    alias: 'keyword',
  },
  'type': {
    pattern: /\s[A-Z][a-zA-Z0-9]*\s/,
    alias: 'function',
    lookbehind: true,
  },
  'arrow': {
    pattern: /->/,
    alias: 'operator',
  },
  'value': {
    pattern: /=\s*(?:'[^']*'|"[^"]*"|\d+\.?\d*|\w+)/,
    inside: {
      'string': /'[^']*'|"[^"]*"/,
      'number': /\d+\.?\d*/,
    },
  },
  'punctuation': /[():,]/,
};

  globalThis.Prism = PrismObject;

  additionalLanguages.forEach((lang) => {
    if (lang === 'php') {
      // eslint-disable-next-line global-require
      require('prismjs/components/prism-markup-templating.js');
    }
    // eslint-disable-next-line global-require, import/no-dynamic-require
    require(`prismjs/components/prism-${lang}`);
  });
  // Clean up and eventually restore former globalThis.Prism object (if any)
  delete globalThis.Prism;
  if (typeof PrismBefore !== 'undefined') {
    globalThis.Prism = PrismObject;
  }
}
