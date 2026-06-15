#ifndef GUARD_HM_H
#define GUARD_HM_H

struct Pokemon;

bool8 IsFieldMoveHM(u16 move);
bool8 CanMonUseHM(struct Pokemon *mon, u16 move);
u8 GetPartyMonForHM(u16 move);

#endif // GUARD_HM_H
