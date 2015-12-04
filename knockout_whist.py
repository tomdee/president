#!/usr/bin/env python
from copy import deepcopy
import random
from framework import GameState, Card, ismcts


class KnockoutWhistState(GameState):
    """ A state of the game Knockout Whist.
        See http://www.pagat.com/whist/kowhist.html for a full description of the rules.
        For simplicity of implementation, this version of the game does not include the "dog's life" rule
        and the trump suit for each round is picked randomly rather than being chosen by one of the players.
    """

    def __init__(self, n):
        """ Initialise the game state. n is the number of players (from 2 to 7).
            """
        GameState.__init__(self)
        self.number_of_players = n
        self.player_to_move = 1
        self.tricks_in_round = 7
        self.player_hands = {p: [] for p in xrange(1, self.number_of_players + 1)}
        self.discards = []
        self.current_trick = []
        self.trump_suit = None
        self.tricks_taken = {}
        self.knocked_out = {p: False for p in
                           xrange(1, self.number_of_players + 1)}
        self._deal()

    def clone(self):
        """ Create a deep clone of this game state.
        """
        st = KnockoutWhistState(self.number_of_players)
        st.player_to_move = self.player_to_move
        st.tricks_in_round = self.tricks_in_round
        st.player_hands = deepcopy(self.player_hands)
        st.discards = deepcopy(self.discards)
        st.current_trick = deepcopy(self.current_trick)
        st.trump_suit = self.trump_suit
        st.tricks_taken = deepcopy(self.tricks_taken)
        st.knocked_out = deepcopy(self.knocked_out)
        return st

    def clone_and_randomize(self, observer):
        """ Create a deep clone of this game state, randomizing any information
        not visible to the specified observer player.
        """
        st = self.clone()

        # The observer can see his own hand and the cards in the current trick,
        # and can remember the cards played in previous tricks
        seen_cards = st.player_hands[observer] + st.discards + \
                     [card for (player, card) in st.current_trick]

        # The observer can't see the rest of the deck
        unseen_cards = [card for card in st._get_card_deck()
                        if card not in seen_cards]

        # _deal the unseen cards to the other players
        random.shuffle(unseen_cards)
        for p in xrange(1, st.number_of_players + 1):
            if p != observer:
                # _deal cards to player p
                # Store the size of player p's hand
                num_cards = len(self.player_hands[p])
                # Give player p the first num_cards unseen cards
                st.player_hands[p] = unseen_cards[:num_cards]
                # Remove those cards from unseen_cards
                unseen_cards = unseen_cards[num_cards:]

        return st

    @staticmethod
    def _get_card_deck():
        """ Construct a standard deck of 52 cards.
        """
        return [Card(rank, suit) for rank in xrange(2, 14 + 1) for suit in
                ['C', 'D', 'H', 'S']]

    def _deal(self):
        """ Reset the game state for the beginning of a new round, and _deal the cards.
        """
        self.discards = []
        self.current_trick = []
        self.tricks_taken = {p: 0 for p in xrange(1, self.number_of_players + 1)}

        # Construct a deck, shuffle it, and _deal it to the players
        deck = self._get_card_deck()
        random.shuffle(deck)
        for p in xrange(1, self.number_of_players + 1):
            self.player_hands[p] = deck[:self.tricks_in_round]
            deck = deck[self.tricks_in_round:]

        # Choose the trump suit for this round
        self.trump_suit = random.choice(['C', 'D', 'H', 'S'])

    def get_next_player(self, p):
        """ Return the player to the left of the specified player, skipping players who have been knocked out
        """
        next_player = (p % self.number_of_players) + 1
        # Skip any knocked-out players
        while next_player != p and self.knocked_out[next_player]:
            next_player = (next_player % self.number_of_players) + 1
        return next_player

    def do_move(self, move):
        """ update a state by carrying out the given move.
            Must update player_to_move.
        """
        # Store the played card in the current trick
        self.current_trick.append((self.player_to_move, move))

        # Remove the card from the player's hand
        self.player_hands[self.player_to_move].remove(move)

        # Find the next player
        self.player_to_move = self.get_next_player(self.player_to_move)

        # If the next player has already played in this trick, then the trick is over
        if any(True for (player, card) in self.current_trick if
               player == self.player_to_move):
            # Sort the plays in the trick: those that followed suit (in ascending rank order), then any trump plays (in ascending rank order)
            (leader, lead_card) = self.current_trick[0]
            suited_plays = [(player, card.rank) for (player, card) in
                           self.current_trick if card.suit == lead_card.suit]
            trump_plays = [(player, card.rank) for (player, card) in
                          self.current_trick if card.suit == self.trump_suit]
            sorted_plays = sorted(suited_plays,
                                 key=lambda (aplayer, rank): rank) + sorted(
                trump_plays, key=lambda (aplayer, rank): rank)
            # The winning play is the last element in sorted_plays
            trick_winner = sorted_plays[-1][0]

            # update the game state
            self.tricks_taken[trick_winner] += 1
            self.discards += [card for (player, card) in self.current_trick]
            self.current_trick = []
            self.player_to_move = trick_winner

            # If the next player's hand is empty, this round is over
            if not self.player_hands[self.player_to_move]:
                self.tricks_in_round -= 1
                self.knocked_out = {
                p: (self.knocked_out[p] or self.tricks_taken[p] == 0) for p in
                xrange(1, self.number_of_players + 1)}
                # If all but one players are now knocked out, the game is over
                if len([x for x in self.knocked_out.itervalues() if
                        x == False]) <= 1:
                    self.tricks_in_round = 0

                self._deal()

    def get_moves(self):
        """ Get all possible moves from this state.
        """
        hand = self.player_hands[self.player_to_move]
        if not self.current_trick:
            # May lead a trick with any card
            return hand
        else:
            (leader, lead_card) = self.current_trick[0]
            # Must follow suit if it is possible to do so
            cards_in_suit = [card for card in hand if card.suit == lead_card.suit]
            if cards_in_suit:
                return cards_in_suit
            else:
                # Can't follow suit, so can play any card
                return hand

    def get_result(self, player):
        """ Get the game result from the viewpoint of player.
        """
        return 0 if (self.knocked_out[player]) else 1

    def __repr__(self):
        """ Return a human-readable representation of the state
        """
        result = "Round %i" % self.tricks_in_round
        result += " | P%i: " % self.player_to_move
        result += ",".join(
            str(card) for card in self.player_hands[self.player_to_move])
        result += " | Tricks: %i" % self.tricks_taken[self.player_to_move]
        result += " | Trump: %s" % self.trump_suit
        result += " | Trick: ["
        result += ",".join(
            ("%i:%s" % (player, card)) for (player, card) in self.current_trick)
        result += "]"
        return result


def play_game():
    """ Play a sample game between two ismcts players.
    """
    state = KnockoutWhistState(4)

    while state.get_moves():
        print str(state)
        # Use different numbers of iterations (simulations, tree nodes) for different players
        if state.player_to_move == 1:
            m = ismcts(rootstate=state, itermax=1000, verbose=False)
        else:
            m = ismcts(rootstate=state, itermax=100, verbose=False)
        print "Best Move: " + str(m) + "\n"
        state.do_move(m)

    someone_won = False
    for p in xrange(1, state.number_of_players + 1):
        if state.get_result(p) > 0:
            print "Player " + str(p) + " wins!"
            someone_won = True
    if not someone_won:
        print "Nobody wins!"


if __name__ == "__main__":
    play_game()