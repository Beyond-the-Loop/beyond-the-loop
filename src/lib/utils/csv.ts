export interface CsvColumnDef<T> {
	header: string;
	accessor: (row: T) => string | number | null | undefined;
}

const SEPARATOR = ';';

function escapeCsvField(value: string): string {
	if (value.includes('"') || value.includes(SEPARATOR) || value.includes('\n') || value.includes('\r')) {
		return `"${value.replace(/"/g, '""')}"`;
	}
	return value;
}

export function generateCsv<T>(rows: T[], columns: CsvColumnDef<T>[]): string {
	const BOM = '\uFEFF';
	const header = columns.map((col) => escapeCsvField(col.header)).join(SEPARATOR);
	const dataLines = rows.map((row) =>
		columns
			.map((col) => {
				const raw = col.accessor(row);
				const str = raw == null ? '' : String(raw);
				return escapeCsvField(str);
			})
			.join(SEPARATOR)
	);
	return BOM + [header, ...dataLines].join('\r\n');
}
