# Storefront Templates

Pre-built storefront templates for the 54Link E-commerce platform.
Each template is a self-contained theme that merchants can apply to their stores.

## Available Templates

| Template           | Description                                            | Best For                  |
| ------------------ | ------------------------------------------------------ | ------------------------- |
| `modern-minimal`   | Clean, minimalist layout with focus on product imagery | Fashion, lifestyle brands |
| `marketplace-grid` | Grid-based layout optimized for large catalogs         | Multi-vendor marketplaces |
| `single-product`   | Hero-focused layout for one hero product with variants | Product launches, DTC     |

## Template Structure

Each template contains:

```
template-name/
├── manifest.json       # Template metadata, color scheme, layout config
├── components.tsx      # React component exports (Header, Footer, ProductCard, etc.)
├── styles.css          # Template-specific styles (CSS variables for customization)
└── preview.png         # Template preview image
```

## Usage

Merchants select a template during store creation or from Store Settings.
The selected template's `manifest.json` defines:

- Color scheme (primary, secondary, accent, background)
- Layout mode (grid, list, hero)
- Typography (font family, heading sizes)
- Header/Footer configuration

Templates support runtime customization via CSS custom properties
set from the store's `settings` JSON (logo, banner, colors).

## Creating Custom Templates

1. Copy an existing template directory
2. Update `manifest.json` with your template metadata
3. Customize `components.tsx` with your layout
4. Override CSS variables in `styles.css`
5. Add a `preview.png` (1200x800)
