#include "global.h"
#include "event_data.h"
#include "hm.h"
#include "item.h"
#include "pokemon.h"
#include "constants/flags.h"
#include "constants/items.h"
#include "constants/moves.h"

struct HMFieldMove
{
    u16 move;
    u16 item;
    u16 badgeFlag;
};

static const struct HMFieldMove sHMFieldMoves[] =
{
    {MOVE_CUT,        ITEM_HM01, FLAG_BADGE01_GET},
    {MOVE_FLY,        ITEM_HM02, FLAG_BADGE06_GET},
    {MOVE_SURF,       ITEM_HM03, FLAG_BADGE05_GET},
    {MOVE_STRENGTH,   ITEM_HM04, FLAG_BADGE04_GET},
    {MOVE_FLASH,      ITEM_HM05, FLAG_BADGE02_GET},
    {MOVE_ROCK_SMASH, ITEM_HM06, FLAG_BADGE03_GET},
    {MOVE_WATERFALL,  ITEM_HM07, FLAG_BADGE08_GET},
    {MOVE_DIVE,       ITEM_HM08, FLAG_BADGE07_GET},
};

static const struct HMFieldMove *GetHMFieldMove(u16 move)
{
    u32 i;

    for (i = 0; i < ARRAY_COUNT(sHMFieldMoves); i++)
    {
        if (sHMFieldMoves[i].move == move)
            return &sHMFieldMoves[i];
    }

    return NULL;
}

bool8 IsFieldMoveHM(u16 move)
{
    return GetHMFieldMove(move) != NULL;
}

bool8 CanMonUseHM(struct Pokemon *mon, u16 move)
{
    const struct HMFieldMove *hm = GetHMFieldMove(move);

    if (hm == NULL
     || !FlagGet(hm->badgeFlag)
     || !CheckBagHasItem(hm->item, 1))
        return FALSE;

    return CanMonLearnTMHM(mon, hm->item - ITEM_TM01) != 0;
}

u8 GetPartyMonForHM(u16 move)
{
    u8 i;

    for (i = 0; i < PARTY_SIZE; i++)
    {
        if (GetMonData(&gPlayerParty[i], MON_DATA_SPECIES) == SPECIES_NONE)
            break;
        if (CanMonUseHM(&gPlayerParty[i], move))
            return i;
    }

    return PARTY_SIZE;
}
