#!/usr/bin/env python
from copy import deepcopy
from operator import attrgetter
import random
import sys
from framework import GameState, Card, ismcts, Deck


# TODO:
# Make it faster? https://cardsource.readthedocs.org/en/latest/
# Make it look better -https://github.com/worldveil/deuces
# Put a UI on it
# Let it play int he real world - http://arnab.org/blog/so-i-suck-24-automating-card-games-using-opencv-and-python
#                               - https://rdmilligan.wordpress.com/2014/08/30/playing-card-detection-using-opencv-mark-v/
# Make two the high card
# Allow it to work with any number of players (pass handling become more complicated)
#
CONSECUTIVE = "CONSECUTIVE"
RUN = "RUN"
QUADS = "QUADS"
TRIPS = "TRIPS"
DUBS = "DUBS"


class PresidentGameState(GameState):
    """
    A state of the game President.
    See https://en.wikipedia.org/wiki/President_(card_game)

    A few house rules/variations are being used
     - A
     - B
    """

    def __init__(self):
        """
        Initialise the game state.
        Always have 2 players

        """
        GameState.__init__(self)
        self.player_to_move = 0
        self.player_hands = [[],[]]
        self.discards = []
        self.current_trick = []
        # Modes can be CONSECUTIVE, DUBS, TRIPS, QUADS, RUN
        self.modes = set()

        self._deal()

    def clone(self):
        """ Create a deep clone of this game state.
        """
        st = PresidentGameState()
        st.player_to_move = self.player_to_move
        st.player_hands = deepcopy(self.player_hands)
        st.discards = deepcopy(self.discards)
        st.current_trick = deepcopy(self.current_trick)
        st.modes = deepcopy(self.modes)
        return st

    def clone_and_randomize(self, observer):
        """ Create a deep clone of this game state, randomizing any information
        not visible to the specified observer player.
        """
        st = self.clone()

        # The observer can see his own hand and the cards in the current trick,
        # and can remember the cards played in previous tricks
        flattened_current_trick =  [a for b in st.current_trick for a in b]
        seen_cards = st.player_hands[observer] + st.discards + flattened_current_trick

        # The observer can't see the rest of the deck
        unseen_cards = [card for card in Deck().cards
                        if card not in seen_cards]

        # deal the unseen cards to the player
        random.shuffle(unseen_cards)

        for p in (0,1):
            if p != observer:
                # deal cards to player p. The players start with 17 cards, so
                # with two players there are 34 cards in total.
                # The player should be dealt 34 - discards - num cards in other players hand.

                # Store the size of player p's hand
                num_cards = 34 - len(self.discards) - len(self.player_hands[observer])

                # Give player p the first num_cards unseen cards
                st.player_hands[p] = unseen_cards[:num_cards]

        return st

    def get_next_player(self, p):
        return (p + 1) % self.number_of_players

    def _deal(self):
        """
        Deal the cards
        """
        # Construct a deck, shuffle it, and deal it to the players
        deck = Deck()
        deck.shuffle()

        # Player zero gets the first 17 cards
        self.player_hands[0] = deck.cards[:17]

        # Player one gets the last 17 cards
        self.player_hands[1] = deck.cards[-17:]

    def do_move(self, move):
        """ update a state by carrying out the given move.
            Must update player_to_move.
        """
        # If the move is "PASS" then the current trick is over
        if "PASS" in move:
            # Trick over so update the game state
            self.discards.extend([a for b in self.current_trick for a in b])
            self.current_trick = []
            self.modes.clear()
        else:
            if len(move) > 1:
                # The player put down multiple cards - add modes
                if move[0].rank == move[1].rank:
                    # Not a sequence
                    if len(move) == 2:
                        self.modes.add(DUBS)
                    elif len(move) == 3:
                        self.modes.add(TRIPS)
                    elif len(move) == 4:
                        self.modes.add(QUADS)
                else:
                    # a sequence
                    self.modes.add(RUN)

            # On the second move, check for CONSECUTIVE mode
            if len(self.current_trick) == 1:
                if DUBS in self.modes or TRIPS in self.modes or QUADS in self.modes \
                    and self.current_trick[0][0].rank + 1 == move.rank[0]:
                    # Just need to check one of the cards in the first hand
                    self.modes.add(CONSECUTIVE)
                elif RUN in self.modes and self.current_trick[0][-1].rank +1 == move.rank[0][0]:
                    # Check the highest card (assume they are ordered) on the first hand.
                    self.modes.add(CONSECUTIVE)
                elif self.current_trick[0][0].rank + 1 == move[0].rank:
                    # print "First card: %s Second Card: %s" % (self.current_trick, move)
                    self.modes.add(CONSECUTIVE)
                    # print self.modes

            # Store the played card in the current trick
            self.current_trick.append(move)

            # Remove the card from the player's hand
            for card in move:
                self.player_hands[self.player_to_move].remove(card)

        # Find the next player - always change players
        self.player_to_move = self.get_next_player(self.player_to_move)


    def get_moves(self):
        """
        Get all possible moves from this state.
        """
        hand = sorted(self.player_hands[self.player_to_move],
                      key=attrgetter('rank', 'suit'))
        if not hand:
            # If there are no moves left, then return the empty list.
            return hand
        if not self.current_trick:
            # May lead a trick with any card. Can't pass - that would be silly.
            # Moves may involve multiple cards, so return a list of lists.
            single_cards = [[card] for card in hand]

            return single_cards
        else:
            # Start by picking out just the higher cards. Card rank needs to be strictly greater.
            # Grab the rank of the last card from the last trick.
            last_card_rank = self.current_trick[-1][-1].rank
            candidate_cards = [card for card in hand if card.rank > last_card_rank]
            moves = []

            for index, card in enumerate(candidate_cards):
                # Make a single loop through the candidate cards and include
                # not just the valid single cards but also the DUBS, TRIPS, QUADS and RUNS.

                # Always include the single cards
                moves.append([card])

                # Now get the list of the higher cards
                next_cards = candidate_cards[index+1:]

                # The aim is to loop over them, until enough cards have been
                # seen to know there aren't any combos (remember they are sorted)
                searched_enough = False

                for next_cards_index, next_card in enumerate(next_cards):
                    # Start looking ahead to find combos
                    if card.rank == next_card.rank:
                        # A pair
                        moves.append([card, next_card])

                        # This is the second next_card - must be TRIPS
                        if next_cards_index == 1:
                            moves.append([card, next_cards[0], next_cards[1]])

                        # This is the third next_card - must be QUADS
                        if next_cards_index == 2:
                            moves.append([card, next_cards[0], next_cards[1], next_cards[2]])

                    if card.rank != next_card.rank:
                        searched_enough = True
                    if searched_enough:
                        break



            # if CONSECUTIVE in self.modes:
            #     moves = [[card] for card in hand if card.rank == last_card_rank + 1]
            # else:
            #

            # If started with a multi card then need to follow
            # If started with a sequence then need to follow
            # If started in consecutive mode then need to follow

            # Can always pass.
            return  moves + [["PASS"]]

    def get_result(self, player):
        """
        Get the game result from the viewpoint of player.
        """
        # If the play has nothing in their hand then they've won.
        return 1 if not self.player_hands[player] else 0

    def __repr__(self):
        """ Return a human-readable representation of the state
        """
        result = "P%i: %s Mode: %s Trick: %s Discards: %s" % (self.player_to_move,
                                                     self.player_hands[self.player_to_move],
                                                     self.modes,
                                                     self.current_trick,
                                                     self.discards)
        return result


def play_game():
    """ Play a sample game between two ismcts players.
    """
    state = PresidentGameState()

    while state.get_moves():
        print str(state)
        # Use different numbers of iterations (simulations, tree nodes) for different players
        if state.player_to_move == 0:
            m = ismcts(rootstate=state, itermax=1000, verbose=False)
        else:
            m = ismcts(rootstate=state, itermax=10, verbose=False)
        print "Best Move: " + str(m) + "\n"
        state.do_move(m)

    someone_won = False
    for p in (0,1):
        if state.get_result(p) > 0:
            print "Player " + str(p) + " wins!"
            someone_won = True
    if not someone_won:
        print "Nobody wins!"


if __name__ == "__main__":
    play_game()