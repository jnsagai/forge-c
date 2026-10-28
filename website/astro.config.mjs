import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import { unified } from "@astrojs/markdown-remark";
import remarkBase from "./scripts/remark-base.mjs";

const base = process.env.BASE_PATH || "/forge-c/";
const site = process.env.SITE_URL || "https://jnsagai.github.io";
if (
  !base.startsWith("/") ||
  !base.endsWith("/") ||
  base.includes("..") ||
  /[?#\\]/.test(base)
) {
  throw new Error(
    "BASE_PATH must be an absolute path ending in /, without traversal, query, or fragment.",
  );
}
if (
  new URL(site).pathname !== "/" ||
  !/^https?:$/.test(new URL(site).protocol)
) {
  throw new Error("SITE_URL must be an HTTP(S) origin.");
}
export default defineConfig({
  site,
  base,
  trailingSlash: "always",
  markdown: { processor: unified({ remarkPlugins: [[remarkBase, { base }]] }) },
  integrations: [
    starlight({
      title: "Forge-C",
      description:
        "An open-source software factory for embedded C drivers, with deterministic checks and offline review evidence.",
      logo: { src: "./src/assets/mark.svg", replacesTitle: false },
      favicon: "/favicon.svg",
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/jnsagai/forge-c",
        },
      ],
      customCss: ["./src/styles/docs.css"],
      editLink: {
        baseUrl: "https://github.com/jnsagai/forge-c/edit/main/website/",
      },
      pagefind: false,
      components: { Search: "./src/components/Search.astro" },
      sidebar: [
        {
          label: "Start here",
          items: [
            { label: "Overview", slug: "docs" },
            {
              label: "Installation",
              slug: "docs/getting-started/installation",
            },
            {
              label: "Your first work order",
              slug: "docs/getting-started/first-work-order",
            },
            { label: "Status & limitations", slug: "docs/status" },
          ],
        },
        {
          label: "Understand the factory",
          items: [{ autogenerate: { directory: "docs/concepts" } }],
        },
        {
          label: "Work with Forge-C",
          items: [{ autogenerate: { directory: "docs/guides" } }],
        },
        {
          label: "Reference",
          items: [
            { label: "Reference overview", slug: "docs/reference" },
            { label: "Commands", slug: "docs/reference/generated/commands" },
            {
              label: "Configuration & contracts",
              slug: "docs/reference/generated/contracts",
            },
            {
              label: "Example work orders",
              slug: "docs/reference/generated/examples",
            },
            {
              label: "Python entry points",
              slug: "docs/reference/generated/python",
            },
          ],
        },
        {
          label: "Development",
          items: [{ autogenerate: { directory: "docs/development" } }],
        },
      ],
    }),
  ],
});
