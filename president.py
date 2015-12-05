#!/usr/bin/env python
from copy import deepcopy
import random
from framework import GameState, Card, ismcts, Deck


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
        self.player_hands = [[],[]]
        self.discards = []
        self.current_trick = []
        self.player_to_move = 0

        self._deal()

    def clone(self):
        """ Create a deep clone of this game state.
        """
        st = PresidentGameState()
        st.player_to_move = self.player_to_move
        st.player_hands = deepcopy(self.player_hands)
        st.discards = deepcopy(self.discards)
        st.current_trick = deepcopy(self.current_trick)
        return st

    def clone_and_randomize(self, observer):
        """ Create a deep clone of this game state, randomizing any information
        not visible to the specified observer player.
        """
        st = self.clone()

        # The observer can see his own hand and the cards in the current trick,
        # and can remember the cards played in previous tricks
        seen_cards = st.player_hands[observer] + st.discards + st.current_trick

        # The observer can't see the rest of the deck
        unseen_cards = [card for card in Deck().cards
                        if card not in seen_cards]

        # _deal the unseen cards to the other players
        random.shuffle(unseen_cards)
        for p in (0,1):
            if p != observer:
                # deal cards to player p. The players start with 17 cards, so
                # with two players there are 34 cards in total.
                # The play should be dealt 34 - discards - num cards in other players hand.

                # Store the size of player p's hand
                num_cards = 34 - len(self.discards) - len(self.player_hands[self.get_next_player(p)])

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
        if move is "PASS":
            # Trick over so update the game state
            self.discards.extend(self.current_trick)
            self.current_trick = []
        else:
            # Store the played card in the current trick
            self.current_trick.append(move)

            # Remove the card from the player's hand
            self.player_hands[self.player_to_move].remove(move)

        # Find the next player - always change players
        self.player_to_move = self.get_next_player(self.player_to_move)


    def get_moves(self):
        """
        Get all possible moves from this state.
        """
        hand = self.player_hands[self.player_to_move]
        if not self.current_trick:
            # May lead a trick with any card. Can't pass - that would be silly.
            return hand
        elif not hand:
            # If there are no moves left, then return the empty list.
            # Don't allow pass, that would be silly.
            return hand
        else:
            # If started with a multi card then need to follow
            # If started with a sequence then need to follow
            # If started in consecutive mode then need to follow

            # Card rank needs to be strictly greater. And can always pass.
            last_card = self.current_trick[-1]
            return [card for card in hand if card.rank > last_card.rank] + ["PASS"]

    def get_result(self, player):
        """
        Get the game result from the viewpoint of player.
        """
        # If the play has nothing in their hand then they've won.
        return 1 if not self.player_hands[player] else 0

    def __repr__(self):
        """ Return a human-readable representation of the state
        """
        result = "P%i: " % self.player_to_move
        result += ",".join(
            str(card) for card in self.player_hands[self.player_to_move])
        result += " | Trick: "
        result += str(self.current_trick)
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