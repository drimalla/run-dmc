import numpy as np
from scipy.sparse import csr_matrix
import theanets as tn
from sklearn.tree import DecisionTreeClassifier
from sklearn.naive_bayes import BernoulliNB
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier, \
    BaggingClassifier, AdaBoostClassifier, GradientBoostingClassifier
try:
    import tensorflow.contrib.learn as skflow
except ImportError:
    print('Tensorflow not installed')

from operator import itemgetter
from scipy.stats import randint as sp_randint
from numpy import random

from sklearn.grid_search import RandomizedSearchCV


class DMCClassifier:
    clf = None

    def __init__(self, X: csr_matrix, Y: np.array, tune_parameters=False):
        assert len(Y) == X.shape[0]
        self.X = X
        self.Y = Y
        self.tune_parameters = tune_parameters

    def __call__(self, X: csr_matrix) -> np.array:
        if self.tune_parameters:
            print(self.clf.get_params().keys())
            try:
                self.estimate_parameters_with_random_search()
            except Exception as e:
                print(e)
                pass
        self.fit()
        return self.predict(X)

    def report(self, grid_scores, n_top=3):
        top_scores = sorted(
            grid_scores, key=itemgetter(1), reverse=True)[:n_top]
        for i, score in enumerate(top_scores):
            print("Model with rank: {0}".format(i + 1))
            print("Mean validation score: {0:.3f} (std: {1:.3f})".format(
                score.mean_validation_score, np.std(score.cv_validation_scores)))
            print("Parameters: {0}".format(score.parameters))
            print("")

    def estimate_parameters_with_random_search(self):
        random_search = RandomizedSearchCV(self.clf, param_distributions=self.param_dist_random,
                                           n_iter=30)
        random_search.fit(self.X, self.Y)
        print("Random Search")
        self.report(random_search.grid_scores_)

    def fit(self):
        self.clf.fit(self.X, self.Y)
        return self

    def predict(self, X: csr_matrix) -> np.array:
        return self.clf.predict(X)

    def predict_proba(self, X: csr_matrix) -> np.array:
        return self.clf.predict_proba(X)


class DecisionTree(DMCClassifier):
    def __init__(self, X: csr_matrix, Y: np.array, tune_parameters=False):
        super().__init__(X, Y, tune_parameters)
        if tune_parameters:
            self.param_dist_random = {'max_depth': sp_randint(1, 100),
                                      'min_samples_leaf': sp_randint(1, 150),
                                      'max_features': sp_randint(1, self.X.shape[1] - 1),
                                      'criterion': ['entropy', 'gini']}
        self.clf = DecisionTreeClassifier()


class Forest(DMCClassifier):
    def __init__(self, X: csr_matrix, Y: np.array, tune_parameters=False):
        super().__init__(X, Y, tune_parameters)
        if tune_parameters:
            self.param_dist_random = {'max_depth': sp_randint(1, 100),
                                      'min_samples_leaf': sp_randint(1, 100),
                                      'max_features': sp_randint(1, self.X.shape[1] - 1),
                                      'criterion': ['entropy', 'gini']}
        self.clf = RandomForestClassifier(n_estimators=100, n_jobs=8)


class NaiveBayes(DMCClassifier):
    clf = BernoulliNB(binarize=True)


class SVM(DMCClassifier):
    def __init__(self, X: csr_matrix, Y: np.array, tune_parameters=False):
        super().__init__(X, Y, tune_parameters)
        if tune_parameters:
            self.param_dist_random = {'shrinking': [True, False],
                                      'kernel': ['linear', 'poly', 'rbf', 'sigmoid'],
                                      'degree': sp_randint(2, 5)}
        self.clf = SVC(kernel='rbf', shrinking=True)

    def predict_proba(self, X: csr_matrix) -> np.array:
        return self.clf.decision_function(X)


class TheanoNeuralNetwork(DMCClassifier):
    def __init__(self, X: csr_matrix, Y: np.array, tune_parameters=False):
        super().__init__(X, Y, tune_parameters=False)
        input_layer, output_layer = self.X.shape[1], len(np.unique(Y))
        inp = tn.layers.base.Input(size=input_layer, sparse='csr')
        self.clf = tn.Classifier(layers=[inp,
                                         (100, 'linear'), (50, 'norm:mean+relu'),
                                         output_layer])

    def fit(self):
        self.clf.train((self.X, self.Y), algo='sgd', learning_rate=.05, momentum=0.9)
        return self


class BagEnsemble(DMCClassifier):
    classifier = None
    estimators = 20
    max_features = .5
    max_samples = .5

    def __init__(self, X: csr_matrix, Y: np.array, tune_parameters=False):
        super().__init__(X, Y, tune_parameters)
        if tune_parameters:
            self.param_dist_random = {'max_features': sp_randint(1, self.X.shape[1]),
                                      'n_estimators': sp_randint(1, 100)}
        self.clf = BaggingClassifier(self.classifier, n_estimators=self.estimators, n_jobs=8,
                                     max_samples=self.max_samples, max_features=self.max_features)


class TreeBag(BagEnsemble):
    classifier = DecisionTreeClassifier()


class SVMBag(DMCClassifier):
    classifier = None
    estimators = 10
    max_features = .5
    max_samples = .5

    def __init__(self, X: csr_matrix, Y: np.array, tune_parameters=False):
        super().__init__(X, Y, tune_parameters)
        self.X, self.Y = X.toarray(), Y
        self.classifier = SVC(decision_function_shape='ovo')
        self.clf = BaggingClassifier(self.classifier, n_estimators=self.estimators, n_jobs=8,
                                     max_samples=self.max_samples, max_features=self.max_features)

    def predict(self, X: csr_matrix):
        X = X.toarray()
        return self.clf.predict(X)


class AdaBoostEnsemble(DMCClassifier):
    classifier = None
    estimators = 800
    learning_rate = .25
    algorithm = 'SAMME.R'

    def __init__(self, X: np.array, Y: np.array, tune_parameters=False):
        super().__init__(X, Y, tune_parameters)
        if tune_parameters:
            self.param_dist_random = {'n_estimators': sp_randint(1, 1000),
                                      'algorithm': ['SAMME', 'SAMME.R'],
                                      'learning_rate': random.random(100)}
            self.param_dist_grid = {'n_estimators': [100, 200, 400, 900, 1000],
                                    'algorithm': ['SAMME', 'SAMME.R'],
                                    'learning_rate': [.1, .2, 0.25, .3,
                                                      .4, .5, .6]}
        self.clf = AdaBoostClassifier(self.classifier,
                                      n_estimators=self.estimators,
                                      learning_rate=self.learning_rate,
                                      algorithm=self.algorithm)


class AdaTree(AdaBoostEnsemble):
    classifier = DecisionTreeClassifier()


class AdaBayes(AdaBoostEnsemble):
    classifier = BernoulliNB()


class AdaSVM(AdaBoostEnsemble):
    algorithm = 'SAMME'

    def __init__(self, X: np.array, Y: np.array, tune_parameters: bool):
        self.classifier = SVC(decision_function_shape='ovo')
        super().__init__(X, Y, tune_parameters)


class GradBoost(DMCClassifier):
    estimators = 2000
    learning_rate = 1
    max_depth = 1
    max_features = 0.97

    def __init__(self, X: np.array, Y: np.array, tune_parameters=False):
        super().__init__(X, Y)
        self.clf = GradientBoostingClassifier(n_estimators=self.estimators,
                                              learning_rate=self.learning_rate,
                                              max_depth=self.max_depth,
                                              max_features=self.max_features)

    def predict(self, X: csr_matrix) -> np.array:
        return self.clf.predict(X.toarray())

    def predict_proba(self, X: csr_matrix):
        return self.clf.predict(X.toarray())


class TensorFlowNeuralNetwork(DMCClassifier):
    steps = 20000
    learning_rate = 0.05
    hidden_units = [100, 100]
    optimizer = 'SGD'

    def __init__(self, X: np.array, Y: np.array, tune_parameters=False):
        super().__init__(X, Y, tune_parameters=False)
        self.X = X.todense()  # TensorFlow/Skflow doesn't support sparse matrices
        output_layer = len(np.unique(Y))
        if tune_parameters:
            self.param_dist_random = {'learning_rate': random.random(100),
                                      'optimizer': ['Adam'],
                                      'hidden_units': [sp_randint(50, 500), sp_randint(50, 500)]}

        self.clf = skflow.TensorFlowDNNClassifier(hidden_units=self.hidden_units,
                                                  n_classes=output_layer, steps=self.steps,
                                                  learning_rate=self.learning_rate, verbose=0,
                                                  optimizer=self.optimizer)

    def predict(self, X: csr_matrix):
        X = X.todense()  # TensorFlow/Skflow doesn't support sparse matrices
        return self.clf.predict(X)

    def predict_proba(self, X: csr_matrix):
        return self.clf.predict_proba(X.todense())
