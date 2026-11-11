import fs from "node:fs";
import path from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

export async function resolve(specifier, context, nextResolve) {
  let target = specifier;
  const isAlias = target.startsWith("@/");
  
  if (isAlias || target.startsWith(".") || target.startsWith("/")) {
    const parentDir = context.parentURL ? path.dirname(fileURLToPath(context.parentURL)) : process.cwd();
    const basePath = isAlias
      ? path.resolve(process.cwd(), target.slice(2))
      : path.resolve(parentDir, target);

    const candidates = [
      basePath,
      basePath + ".ts",
      basePath + ".tsx",
      basePath + ".js",
      basePath + ".mjs",
      path.join(basePath, "index.ts"),
      path.join(basePath, "index.tsx"),
      path.join(basePath, "index.js"),
    ];

    for (const c of candidates) {
      if (fs.existsSync(c) && !fs.statSync(c).isDirectory()) {
        return {
          url: pathToFileURL(c).href,
          shortCircuit: true,
        };
      }
    }
  }

  return nextResolve(specifier, context);
}
