import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dataPath = "/Users/azrilhilmi/Documents/New project/outputs/pdf_extract/quotation_data.json";
const outputDir = "/Users/azrilhilmi/Documents/New project/outputs/pdf_extract";
const outputPath = `${outputDir}/PHARMACY - Quotation 22052025_LH.xlsx`;

const payload = JSON.parse(await fs.readFile(dataPath, "utf8"));
const workbook = Workbook.create();

function colName(n) {
  let s = "";
  while (n > 0) {
    const m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function rangeFor(topLeftCol, topLeftRow, colCount, rowCount) {
  const endCol = colName(topLeftCol + colCount - 1);
  const endRow = topLeftRow + rowCount - 1;
  return `${colName(topLeftCol)}${topLeftRow}:${endCol}${endRow}`;
}

const itemsSheet = workbook.worksheets.getOrAdd("Quotation Items", {
  renameFirstIfOnlyNewSpreadsheet: true,
});

const headers = [
  "Section",
  "Subsection",
  "Code Number",
  "Material Code",
  "DCHA Material Code",
  "Item Description",
  "EA",
  "1-14 Boxes",
  ">=15 Boxes",
  "Retail RSP Price",
  "Source Page",
];

const rows = payload.items.map((item) => [
  item.section,
  item.subsection,
  item.code_number,
  item.material_code,
  item.dcha_material_code,
  item.item_description,
  item.ea,
  item.price_1_14_boxes,
  item.price_15_plus_boxes,
  item.retail_rsp_price,
  item.page,
]);

const tableValues = [headers, ...rows];
itemsSheet.getRange(rangeFor(1, 1, headers.length, tableValues.length)).values = tableValues;

itemsSheet.freezePanes.freezeRows(1);
itemsSheet.getRange("A1:K1").format.fill = "#1F4E78";
itemsSheet.getRange("A1:K1").format.font = { bold: true, color: "#FFFFFF" };
itemsSheet.getRange("A1:K1").format.wrapText = true;
itemsSheet.getRange("A1:K1").format.horizontalAlignment = "center";
itemsSheet.getRange(`A2:K${tableValues.length}`).format.borders = {
  preset: "inside",
  style: "thin",
  color: "#E5E7EB",
};
itemsSheet.getRange(`A1:K${tableValues.length}`).format.borders = {
  preset: "outside",
  style: "thin",
  color: "#9CA3AF",
};
itemsSheet.getRange(`G2:G${tableValues.length}`).format.numberFormat = "0";
itemsSheet.getRange(`H2:J${tableValues.length}`).format.numberFormat = "#,##0.00";
itemsSheet.getRange(`K2:K${tableValues.length}`).format.numberFormat = "0";
itemsSheet.getRange(`A1:K${tableValues.length}`).format.autofitRows();

const widths = [210, 155, 105, 130, 125, 320, 60, 90, 90, 110, 85];
for (let i = 0; i < widths.length; i++) {
  itemsSheet.getRange(`${colName(i + 1)}1:${colName(i + 1)}${tableValues.length}`).format.columnWidthPx = widths[i];
}
itemsSheet.getRange(`F2:F${tableValues.length}`).format.wrapText = true;
itemsSheet.getRange(`A2:B${tableValues.length}`).format.wrapText = true;

const notesSheet = workbook.worksheets.add("Quotation Notes");
const notesRows = [
  ["Field", "Value"],
  ...Object.entries(payload.notes),
  ["Extracted product rows", payload.row_count],
];
notesSheet.getRange(rangeFor(1, 1, 2, notesRows.length)).values = notesRows;
notesSheet.getRange("A1:B1").format.fill = "#1F4E78";
notesSheet.getRange("A1:B1").format.font = { bold: true, color: "#FFFFFF" };
notesSheet.getRange(`A1:B${notesRows.length}`).format.borders = {
  preset: "inside",
  style: "thin",
  color: "#E5E7EB",
};
notesSheet.getRange(`A1:B${notesRows.length}`).format.borders = {
  preset: "outside",
  style: "thin",
  color: "#9CA3AF",
};
notesSheet.getRange(`A1:B${notesRows.length}`).format.autofitRows();
notesSheet.getRange("A1:A20").format.columnWidthPx = 180;
notesSheet.getRange("B1:B20").format.columnWidthPx = 620;
notesSheet.getRange("B2:B20").format.wrapText = true;
notesSheet.freezePanes.freezeRows(1);

const previewItems = await workbook.inspect({
  kind: "table",
  range: "Quotation Items!A1:K12",
  include: "values",
  tableMaxRows: 12,
  tableMaxCols: 11,
});
console.log(previewItems.ndjson);

const errorScan = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errorScan.ndjson);

await workbook.render({ sheetName: "Quotation Items", range: "A1:K20", scale: 1 });
await workbook.render({ sheetName: "Quotation Notes", range: "A1:B10", scale: 1 });

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
