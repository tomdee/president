#!/usr/bin/env python
from copy import copy
from operator import attrgetter
import random
import sys

from blessings import Terminal

from framework import GameState, Card, ismcts, Deck


# TODO:
# Make it faster? https://cardsource.readthedocs.org/en/latest/
# Make it look better - https://github.com/worldveil/deuces
# Let it play int he real world - http://arnab.org/blog/so-i-suck-24-automating-card-games-using-opencv-and-python
#                               - https://rdmilligan.wordpress.com/2014/08/30/playing-card-detection-using-opencv-mark-v/
# Allow it to work with any number of players (pass handling become more complicated)
# WOrk with Jokers

# run exclusivity
# Make sure sorted
CLEAN_PACK = Deck().cards
term = Terminal()

class PresidentGameState(GameState):
    """
    A state of the game President.
    See https://en.wikipedia.org/wiki/President_(card_game)
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
        self.on_the_table = []
        self.combo_size = 0
        self.consecutive_mode = 0
        self.straight_length = 0

    def clone(self):
        """ Create a deep clone of this game state.
        """
        st = PresidentGameState()
        st.player_to_move = self.player_to_move
        st.player_hands = [copy(self.player_hands[0]), copy(self.player_hands[1])]
        st.discards = copy(self.discards)
        st.on_the_table = copy(self.on_the_table)
        st.combo_size = self.combo_size
        st.consecutive_mode = self.consecutive_mode
        st.straight_length = self.straight_length

        return st

    def clone_and_randomize(self, observer):
        """ Create a deep clone of this game state, randomizing any information
        not visible to the specified observer player.
        """
        st = self.clone()

        # The observer can see his own hand and the cards in the current trick,
        # and can remember the cards played in previous tricks
        flattened_current_trick =  [a for b in st.on_the_table for a in b]
        seen_cards = set(st.player_hands[observer] + st.discards + flattened_current_trick)

        # The observer can't see the rest of the deck
        unseen_cards = [card for card in CLEAN_PACK
                        if card not in seen_cards]

        # deal the unseen cards to the player
        random.shuffle(unseen_cards)

        for p in (0,1):
            if p != observer:
                # deal cards to player p. The players start with 17 cards, so
                # with two players there are 34 cards in total.
                # The player should be dealt 34 - discards - num cards in other players hand.

                # Store the size of player p's hand
                num_cards = 34 - len(st.discards) - len(st.player_hands[observer])

                # Give player p the first num_cards unseen cards
                st.player_hands[p] = sorted(unseen_cards[:num_cards],
                                            key=attrgetter('rank', 'suit'))

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
        self.player_hands[0] = sorted(deck.cards[:17],
                                      key=attrgetter('rank', 'suit'))

        # Player one gets the last 17 cards
        self.player_hands[1] = sorted(deck.cards[-17:],
                                      key=attrgetter('rank', 'suit'))

    def do_move(self, move):
        """ update a state by carrying out the given move.
            Must update player_to_move.
        """
        # If the move is "PASS" then the current trick is over
        if move is "PASS":
            # Trick over so update the game state
            self.discards.extend([a for b in self.on_the_table for a in b])
            self.on_the_table = []
            self.straight_length = 0
            self.consecutive_mode = 0
            self.combo_size = 0
            self.player_to_move = self.get_next_player(self.player_to_move)
        else:
            if len(move) > 1:
                # The player put down multiple cards - add modes
                if move[0].rank == move[1].rank:
                    self.combo_size = len(move)
                else:
                    self.straight_length = len(move)

            # On the second move, check for CONSECUTIVE mode
            if len(self.on_the_table) == 1:
                # Check the highest card (TODO assume they are ordered) on the first hand.
                if self.on_the_table[0][-1].rank + 1 == move[0].rank:
                    self.consecutive_mode = 1

            # Store the played card in the current trick
            self.on_the_table.append(move)

            # Remove the card from the player's hand
            # TODO - this is probably slow
            for card in move:
                self.player_hands[self.player_to_move].remove(card)

            if self.player_hands[self.player_to_move]:
                # Only change players if the current player didn't just finish
                # If the current player finished, then we want to generate no
                # moves for that player to signal the end of hte game
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
        else:
            if not self.on_the_table:
                # May lead a trick with any card. Can't pass - that would be silly.
                # Moves may involve multiple cards, so return a list of lists.
                candidate_cards = hand
            else:
                # Start by picking out just the higher cards. Card rank needs to be strictly greater.
                # Grab the rank of the last card from the last trick.
                minimum_rank = self.on_the_table[-1][-1].rank + 1

                if self.consecutive_mode:
                    if self.straight_length > 0:
                        # This is a straight - therefore we have a min and max range
                        candidate_cards = [card for card in hand if card.rank >= minimum_rank and card.rank < minimum_rank + self.straight_length]
                    else:
                        # Not a straight - therefore an exact rank is required
                        candidate_cards = [card for card in hand if card.rank == minimum_rank]
                else:
                    candidate_cards = [card for card in hand if card.rank >= minimum_rank]

            moves = []
            # TODO - alternative implementation for finding straights -
            # Split the deck by suit, and only both search suits that have more than three cards.


            for index, card in enumerate(candidate_cards):
                # Make a single loop through the candidate cards and include
                # not just the valid single card plays but also the DUBS, TRIPS, QUADS and RUNS.
                straight_found = [card]

                if self.combo_size == 0 and self.straight_length == 0:
                    # Always include the single cards when not in combo mode
                    moves.append([card])

                if not self.on_the_table or self.combo_size > 0 or self.straight_length > 0:
                    # It's either the first hand, or playing to a straight or combo. There's more work to do...
                    # Now get the list of the higher cards
                    next_cards = candidate_cards[index+1:]

                    for next_cards_index, next_card in enumerate(next_cards):

                        if not self.on_the_table or (self.combo_size > 0 and self.straight_length == 0):
                            # Start looking ahead to find combos
                            if card.rank == next_card.rank:
                                if not self.on_the_table or self.combo_size == 2:
                                    # A pair
                                    moves.append([card, next_card])

                                if not self.on_the_table or self.combo_size == 3:
                                    # This is the second next_card - must be TRIPS
                                    if next_cards_index == 1:
                                        moves.append([card, next_cards[0], next_cards[1]])

                                if not self.on_the_table or self.combo_size == 4:
                                    # This is the third next_card - must be QUADS
                                    if next_cards_index == 2:
                                        moves.append([card, next_cards[0], next_cards[1], next_cards[2]])

                        if not self.on_the_table or self.straight_length > 0:
                            # Start looking ahead to find straights
                            # Check the last card found in the run found so far. Add the card to the list if it's good.
                            if straight_found[-1].rank + 1 == next_card.rank and straight_found[-1].suit == next_card.suit:
                                straight_found.append(next_card)
                                if not self.on_the_table and len(straight_found) >= 3:
                                    # Opening move and the straight is at least three long. Record it.
                                    moves.append(copy(straight_found))
                                elif self.on_the_table and len(straight_found) == self.straight_length:
                                    # A straight long enough to play on a previous straight has been found.
                                    moves.append(straight_found)

            # Can always pass.
            return  moves + ["PASS"]

    def get_result(self, player):
        """
        Get the game result from the viewpoint of player.
        """
        # If the play has nothing in their hand then they've won.
        return 1 if not self.player_hands[player] else 0

    def __repr__(self):
        """ Return a human-readable representation of the state
        """
        result = "P%i: %s Consec: %s Combo: %s Straight: %s Trick: %s Discards: %s" % (
        self.player_to_move,
        self.player_hands[self.player_to_move],
        # self.player_hands,
        self.consecutive_mode,
        self.combo_size,
        self.straight_length,
        self.on_the_table,
        self.discards)
        return result


def play_self():
    """ Play a sample game between two ismcts players.
    """
    state = PresidentGameState()
    state._deal()

    while state.get_moves():
        print str(state)
        # Use different numbers of iterations (simulations, tree nodes) for different players
        if state.player_to_move == 0:
            m = ismcts(rootstate=state, itermax=1000, verbose=False)
        else:
            m = ismcts(rootstate=state, itermax=100, verbose=False)
        print "Best Move: " + str(m) + "\n"
        state.do_move(m)

    for p in (0,1):
        if state.get_result(p) > 0:
            print "Player " + str(p) + " wins!"


def get_card(prompt):
    card = None

    while not card:
        try:
            card = Card(raw_input(prompt).upper())
        except Exception:
            print "Bad card - try again"
    return card


def get_int(prompt):
    input = None

    while input is None:
        try:
            input = int(raw_input(prompt))
        except Exception:
            print "Bad input - try again"
    return input


def play_game():
    """ Play a game between one human and one AI
    """
    state = PresidentGameState()
    # state.player_hands[0] = [
    #                          Card('3H'),
    #                          Card('4H'),
    #                          Card('5C'),
    #                          Card('5D'),
    #                          Card('6H'),
    #                          Card('7H'),
    #                          Card('8C'),
    #                          Card('9H'),
    #                          Card('JH'),
    #                          Card('QH'),
    #                          Card('KC'),
    #                          Card('AH'),
    #                          Card('2H'),
    #                          Card('QD'),
    #                          Card('KS'),
    #                          Card('AD'),
    #                          Card('2D')]
    state.player_hands[0] = [
                         Card('9d'),
                         Card('js'),
                         Card('qc'),
                         Card('3d'),
                         Card('as'),
                         Card('2s'),
                         Card('ts'),
                         Card('jd'),
                         Card('6s'),
                         Card('9s'),
                         Card('5h'),
                         Card('7d'),
                         Card('8s'),
                         Card('4d'),
                         Card('qs'),
                         Card('tc'),
                         Card('7s')]


    TOTAL_CARDS = 17
    while len(state.player_hands[0]) < TOTAL_CARDS:
        card = get_card("Enter card %s/%s: " % (len(state.player_hands[0]) + 1, TOTAL_CARDS))
        if card not in state.player_hands[0]:
            state.player_hands[0].append(card)
        else:
            print "Duplicate card - ignoring"

    print "All done"
    print state.player_hands[0]

    while True:
        print str(state)
        # Use different numbers of iterations (simulations, tree nodes) for different players
        if state.player_to_move == 0:
            m = ismcts(rootstate=state, itermax=10000, verbose=False)
            print "Best Move: " + str(m) + "\n"
            state.do_move(m)
            if not state.player_hands[0]:
                # No cards left - the end
                break

        else:
            confirmed_move = False
            move = []
            while not confirmed_move:
                num_cards = get_int("How many cards did the other player play?")
                move = []
                if num_cards == 0:
                    move = "PASS"
                else:
                    for i in range(num_cards):
                        card = get_card("What was the card?")
                        move.append(card)


                user_input = raw_input("Did the player play this (y/n)? %s" % move)
                if user_input is "y" or user_input is "Y":
                    confirmed_move = True
                else:
                    print "Let's try again..."

            if move is not "PASS":
                state.player_hands[1].extend(move)
            state.do_move(move)
            
            if move is not "PASS":
                state.player_to_move = state.get_next_player(state.player_to_move)

    for p in (0,1):
        if state.get_result(p) > 0:
            print "Player " + str(p) + " wins!"


def test_iters():
    # I want to know how many iteractions are good.
    # I'll play a player that does only 10 iterations, then keep pushing mine up to see how many wins/losses

    # Play this many games at each iter value
    NUM_GAMES = 100

    for iterations in (1, 10, 100, 1000, 10000):

        win_counts = [0,0]
        for game_num in range(NUM_GAMES):
            state = PresidentGameState()
            state._deal()

            with term.location(0, term.height - 1):
                print("(%s) Game number %s/%s" % (iterations, game_num, NUM_GAMES)),
                sys.stdout.flush()

            while state.get_moves():
                # Use different numbers of iterations (simulations, tree nodes) for different players
                if state.player_to_move == 0:
                    m = ismcts(rootstate=state, itermax=iterations, verbose=False, quiet=True)
                else:
                    m = ismcts(rootstate=state, itermax=1, verbose=False, quiet=True)
                # print "Best Move: " + str(m) + "\n"
                state.do_move(m)

            # print "Results: P0: %s P1: %s" % (state.get_result(0), state.get_result(1))
            # if (state.get_result(0) and state.get_result(1)) or not (state.get_result(0) or state.get_result(1)):
            #     # Nobody won or both players won
            #     print state
            for p in (0,1):
                win_counts[p] += state.get_result(p)
        term.clear_eol()
        print "Iteration %s - %s" % (iterations, win_counts)



if __name__ == "__main__":
    play_game()
    # play_self()
    # test_iters()