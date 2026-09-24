/** Rasterises a rendered Recharts <svg> to a PNG data URL so it can be
 * embedded in the jsPDF report. Recharts draws charts as inline SVG (its
 * legend/tooltip are HTML and are not captured -- the report draws its own
 * legend), so serialising the SVG node is enough; no html2canvas needed. */
export interface ChartImage { url: string; width: number; height: number }

export async function svgToPng(svg: SVGSVGElement, scale = 2): Promise<ChartImage> {
  const rect = svg.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width));
  const height = Math.max(1, Math.round(rect.height));

  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(width));
  clone.setAttribute("height", String(height));
  // CSS classes don't travel with a serialised SVG, so pin the font here.
  clone.style.fontFamily = "Helvetica, Arial, sans-serif";

  const xml = new XMLSerializer().serializeToString(clone);
  const src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(xml)}`;

  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new Image();
    el.onload = () => resolve(el);
    el.onerror = () => reject(new Error("Could not render chart to image"));
    el.src = src;
  });

  const canvas = document.createElement("canvas");
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas is not available");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return { url: canvas.toDataURL("image/png"), width, height };
}
