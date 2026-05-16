/** Shared state so only one Popover can be open at a time. */
let current = $state<symbol | null>(null);

export function getOpenId() {
	return current;
}

export function setOpenId(id: symbol | null) {
	current = id;
}
