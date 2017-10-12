from __future__ import absolute_import, print_function

import unittest
import tensorflow as tf
import numpy as np

import gpflow
from gpflow.test_util import GPflowTestCase
from gpflow import decors

from .reference import referenceRbfKernel, referenceArcCosineKernel, referencePeriodicKernel

class TestRbf(GPflowTestCase):
    def test_1d(self):
        with self.test_context():
            lengthscale = 1.4
            variance = 2.3
            kernel = gpflow.kernels.RBF(1)
            kernel.lengthscales = lengthscale
            kernel.variance = variance
            rng = np.random.RandomState(1)

            X = tf.placeholder(tf.float64)
            X_data = rng.randn(3, 1)

            kernel.compile()
            gram_matrix = kernel.session.run(kernel.K(X), feed_dict={X: X_data})
            reference_gram_matrix = referenceRbfKernel(X_data, lengthscale, variance)
            self.assertTrue(np.allclose(gram_matrix, reference_gram_matrix))


class TestArcCosine(GPflowTestCase):
    def evalKernelError(self, D, variance, weight_variances,
                        bias_variance, order, ARD, X_data):
        with self.test_context():
            kernel = gpflow.kernels.ArcCosine(
                D,
                order=order,
                variance=variance,
                weight_variances=weight_variances,
                bias_variance=bias_variance,
                ARD=ARD)

            if weight_variances is None:
                weight_variances = 1.
            kernel.compile()
            X = tf.placeholder(tf.float64)
            gram_matrix = kernel.session.run(kernel.K(X), feed_dict={X: X_data})
            reference_gram_matrix = referenceArcCosineKernel(
                X_data, order,
                weight_variances,
                bias_variance,
                variance)

            self.assertTrue(np.allclose(gram_matrix, reference_gram_matrix))

    def test_1d(self):
        with self.test_context():
            D = 1
            N = 3
            weight_variances = 1.7
            bias_variance = 0.6
            variance = 2.3
            ARD = False
            orders = gpflow.kernels.ArcCosine.implemented_orders

            rng = np.random.RandomState(1)
            X_data = rng.randn(N, D)
            for order in orders:
                self.evalKernelError(D, variance, weight_variances,
                                     bias_variance, order, ARD, X_data)

    def test_3d(self):
        with self.test_context():
            D = 3
            N = 8
            weight_variances = np.array([0.4, 4.2, 2.3])
            bias_variance = 1.9
            variance = 1e-2
            ARD = True
            orders = gpflow.kernels.ArcCosine.implemented_orders

            rng = np.random.RandomState(1)
            X_data = rng.randn(N, D)
            for order in orders:
                self.evalKernelError(D, variance, weight_variances,
                                     bias_variance, order, ARD, X_data)

    def test_non_implemented_order(self):
        with self.test_context(), self.assertRaises(ValueError):
            gpflow.kernels.ArcCosine(1, order=42)

    def test_weight_initializations(self):
        with self.test_context():
            D = 1
            N = 3
            weight_variances = None
            bias_variance = 1.
            variance = 1.
            ARDs = {False, True}
            order = 0

            rng = np.random.RandomState(1)
            X_data = rng.randn(N, D)
            for ARD in ARDs:
                self.evalKernelError(
                    D, variance, weight_variances,
                    bias_variance, order, ARD, X_data)

    def test_nan_in_gradient(self):
        with self.test_context():
            D = 1
            N = 4

            rng = np.random.RandomState(23)
            X_data = rng.rand(N, D)
            kernel = gpflow.kernels.ArcCosine(D)

            X = tf.placeholder(tf.float64)
            kernel.compile()
            grads = tf.gradients(kernel.K(X), X)
            gradients = kernel.session.run(grads, feed_dict={X: X_data})
            self.assertFalse(np.any(np.isnan(gradients)))


class TestPeriodic(GPflowTestCase):
    def evalKernelError(self, D, lengthscale, variance, period, X_data):
        with self.test_context():
            kernel = gpflow.kernels.PeriodicKernel(
                D, period=period, variance=variance, lengthscales=lengthscale)

            X = tf.placeholder(tf.float64)
            reference_gram_matrix = referencePeriodicKernel(
                X_data, lengthscale, variance, period)
            kernel.compile()
            gram_matrix = kernel.session.run(kernel.K(X), feed_dict={X: X_data})
            self.assertTrue(np.allclose(gram_matrix, reference_gram_matrix))

    def test_1d(self):
        with self.test_context():
            D = 1
            lengthScale = 2
            variance = 2.3
            period = 2
            rng = np.random.RandomState(1)
            X_data = rng.randn(3, 1)
            self.evalKernelError(D, lengthScale, variance, period, X_data)

    def test_2d(self):
        with self.test_context():
            D = 2
            N = 5
            lengthScale = 11.5
            variance = 1.3
            period = 20
            rng = np.random.RandomState(1)
            X_data = rng.multivariate_normal(np.zeros(D), np.eye(D), N)
            self.evalKernelError(D, lengthScale, variance, period, X_data)


class TestCoregion(GPflowTestCase):
    def setUp(self):
        self.rng = np.random.RandomState(0)
        self.k = gpflow.kernels.Coregion(1, output_dim=3, rank=2)
        self.k.W = self.rng.randn(3, 2)
        self.k.kappa = self.rng.rand(3) + 1.
        self.X = np.random.randint(0, 3, (10, 1))
        self.X2 = np.random.randint(0, 3, (12, 1))

    def tearDown(self):
        GPflowTestCase.tearDown(self)
        self.k.clear()

    def test_shape(self):
        with self.test_context():
            self.k.compile()
            K = self.k.compute_K(self.X, self.X2)
            self.assertTrue(K.shape == (10, 12))
            K = self.k.compute_K_symm(self.X)
            self.assertTrue(K.shape == (10, 10))

    def test_diag(self):
        with self.test_context():
            self.k.compile()
            K = self.k.compute_K_symm(self.X)
            Kdiag = self.k.compute_Kdiag(self.X)
            self.assertTrue(np.allclose(np.diag(K), Kdiag))

    def test_slice(self):
        with self.test_context():
            # compute another kernel with additinoal inputs,
            # make sure out kernel is still okay.
            X = np.hstack((self.X, self.rng.randn(10, 1)))
            k1 = gpflow.kernels.Coregion(1, 3, 2, active_dims=[0])
            k2 = gpflow.kernels.RBF(1, active_dims=[1])
            k = k1 * k2
            k.compile()
            K1 = k.compute_K_symm(X)
            K2 = k1.compute_K_symm(X) * k2.compute_K_symm(X)  # slicing happens inside kernel
            self.assertTrue(np.allclose(K1, K2))


class TestKernSymmetry(GPflowTestCase):
    def setUp(self):
        self.kernels = [gpflow.kernels.Constant,
                        gpflow.kernels.Linear,
                        gpflow.kernels.Polynomial,
                        gpflow.kernels.ArcCosine]
        self.kernels += gpflow.kernels.Stationary.__subclasses__()
        self.rng = np.random.RandomState()

    def test_1d(self):
        with self.test_context():
            kernels = [K(1) for K in self.kernels]
            for kernel in kernels:
                kernel.compile()
            X = tf.placeholder(tf.float64)
            X_data = self.rng.randn(10, 1)
            for k in kernels:
                errors = k.session.run(k.K(X) - k.K(X, X), feed_dict={X: X_data})
                self.assertTrue(np.allclose(errors, 0))

    def test_5d(self):
        with self.test_context():
            kernels = [K(5) for K in self.kernels]
            for kernel in kernels:
                kernel.compile()
            X = tf.placeholder(tf.float64)
            X_data = self.rng.randn(10, 5)
            for k in kernels:
                errors = k.session.run(k.K(X) - k.K(X, X), feed_dict={X: X_data})
                self.assertTrue(np.allclose(errors, 0))


class TestKernDiags(GPflowTestCase):
    def setUp(self):
        with self.test_context():
            inputdim = 3
            rng = np.random.RandomState(1)
            self.rng = rng
            self.dim = inputdim
            self.kernels = [k(inputdim) for k in gpflow.kernels.Stationary.__subclasses__() +
                            [gpflow.kernels.Constant,
                             gpflow.kernels.Linear,
                             gpflow.kernels.Polynomial]]
            self.kernels.append(gpflow.kernels.RBF(inputdim) + gpflow.kernels.Linear(inputdim))
            self.kernels.append(gpflow.kernels.RBF(inputdim) * gpflow.kernels.Linear(inputdim))
            self.kernels.append(gpflow.kernels.RBF(inputdim) +
                                gpflow.kernels.Linear(
                                    inputdim, ARD=True, variance=rng.rand(inputdim)))
            self.kernels.append(gpflow.kernels.PeriodicKernel(inputdim))
            self.kernels.extend(gpflow.kernels.ArcCosine(inputdim, order=order)
                                for order in gpflow.kernels.ArcCosine.implemented_orders)

    def test(self):
        with self.test_context():
            for k in self.kernels:
                k.compile()
                X = tf.placeholder(tf.float64, [30, self.dim])
                rng = np.random.RandomState(1)
                X_data = rng.randn(30, self.dim)
                k1 = k.Kdiag(X)
                k2 = tf.diag_part(k.K(X))
                k1, k2 = k.session.run([k1, k2], feed_dict={X: X_data})
                self.assertTrue(np.allclose(k1, k2))


class TestAdd(GPflowTestCase):
    """
    add a rbf and linear kernel, make sure the result is the same as adding
    the result of the kernels separaetely
    """

    def setUp(self):
        rbf = gpflow.kernels.RBF(1)
        lin = gpflow.kernels.Linear(1)
        k = gpflow.kernels.RBF(1, name='RBFInAdd') + gpflow.kernels.Linear(1, name='LinearInAdd')
        self.rng = np.random.RandomState(0)
        self.kernels = [rbf, lin, k]

    def test_sym(self):
        with self.test_context():
            X = tf.placeholder(tf.float64)
            X_data = self.rng.randn(10, 1)
            res = []
            for k in self.kernels:
                k.compile()
                res.append(k.session.run(k.K(X), feed_dict={X: X_data}))
            self.assertTrue(np.allclose(res[0] + res[1], res[2]))

    def test_asym(self):
        with self.test_context():
            X = tf.placeholder(tf.float64)
            Z = tf.placeholder(tf.float64)
            X_data = self.rng.randn(10, 1)
            Z_data = self.rng.randn(12, 1)
            res = []
            for k in self.kernels:
                k.compile()
                res.append(k.session.run(k.K(X, Z), feed_dict={X: X_data, Z: Z_data}))
            self.assertTrue(np.allclose(res[0] + res[1], res[2]))


class TestWhite(GPflowTestCase):
    """
    The white kernel should not give the same result when called with k(X) and
    k(X, X)
    """

    def test(self):
        with self.test_context():
            rng = np.random.RandomState(0)
            X = tf.placeholder(tf.float64)
            X_data = rng.randn(10, 1)
            k = gpflow.kernels.White(1)
            k.compile()
            K_sym = k.session.run(k.K(X), feed_dict={X: X_data})
            K_asym = k.session.run(k.K(X, X), feed_dict={X: X_data})
            self.assertFalse(np.allclose(K_sym, K_asym))


class TestSlice(GPflowTestCase):
    """
    Make sure the results of a sliced kernel is the same as an unsliced kernel
    with correctly sliced data...
    """

    def setUp(self):
        with self.test_context():
            kernels = [gpflow.kernels.Constant,
                       gpflow.kernels.Linear,
                       gpflow.kernels.Polynomial]
            kernels += gpflow.kernels.Stationary.__subclasses__()
            self.kernels = []
            kernname = lambda cls, index: '_'.join([cls.__name__, str(index)])
            for kernclass in kernels:
                k1 = kernclass(1, active_dims=[0], name=kernname(kernclass, 1))
                k2 = kernclass(1, active_dims=[1], name=kernname(kernclass, 2))
                k3 = kernclass(1, active_dims=slice(0, 1), name=kernname(kernclass, 3))
                self.kernels.append([k1, k2, k3])

    def test_symm(self):
        for k1, k2, k3 in self.kernels:
            with self.test_context():
                rng = np.random.RandomState(0)
                X = rng.randn(20, 2)
                print("k1: {0}, k2: {1}, k3: {2}".format(k1, k2, k3))
                k1.compile()
                k2.compile()
                k3.compile()
                K1 = k1.compute_K_symm(X)
                K2 = k2.compute_K_symm(X)
                K3 = k3.compute_K_symm(X[:, :1])
                K4 = k3.compute_K_symm(X[:, 1:])
                self.assertTrue(np.allclose(K1, K3))
                self.assertTrue(np.allclose(K2, K4))

    def test_asymm(self):
        for k1, k2, k3 in self.kernels:
            with self.test_context():
                rng = np.random.RandomState(0)
                X = rng.randn(20, 2)
                Z = rng.randn(10, 2)
                k1.compile()
                k2.compile()
                k3.compile()
                K1 = k1.compute_K(X, Z)
                K2 = k2.compute_K(X, Z)
                K3 = k3.compute_K(X[:, :1], Z[:, :1])
                K4 = k3.compute_K(X[:, 1:], Z[:, 1:])
                self.assertTrue(np.allclose(K1, K3))
                self.assertTrue(np.allclose(K2, K4))


class TestProd(GPflowTestCase):
    def setUp(self):
        with self.test_context():
            k1 = gpflow.kernels.Matern32(2)
            k2 = gpflow.kernels.Matern52(2, lengthscales=0.3)
            k3 = k1 * k2
            self.kernels = [k1, k2, k3]

    def tearDown(self):
        GPflowTestCase.tearDown(self)
        self.kernels[2].clear()

    def test_prod(self):
        with self.test_context():
            self.kernels[2].compile()

            X = tf.placeholder(tf.float64, [30, 2])
            X_data = np.random.randn(30, 2)

            res = []
            for kernel in self.kernels:
                K = kernel.K(X)
                res.append(kernel.session.run(K, feed_dict={X: X_data}))

            self.assertTrue(np.allclose(res[0] * res[1], res[2]))


class TestARDActiveProd(GPflowTestCase):
    def setUp(self):
        self.rng = np.random.RandomState(0)

        # k3 = k1 * k2
        self.k1 = gpflow.kernels.RBF(3, active_dims=[0, 1, 3], ARD=True)
        self.k2 = gpflow.kernels.RBF(1, active_dims=[2], ARD=True)
        self.k3 = gpflow.kernels.RBF(4, ARD=True)
        self.k1.lengthscales = np.array([3.4, 4.5, 5.6])
        self.k2.lengthscales = np.array([6.7])
        self.k3.lengthscales = np.array([3.4, 4.5, 6.7, 5.6])
        self.k3a = self.k1 * self.k2

        # make kernel functions in python

    def test(self):
        with self.test_context():
            X = tf.placeholder(tf.float64, [50, 4])
            X_data = np.random.randn(50, 4)
            self.k3.compile()
            self.k3a.compile()
            K1 = self.k3.K(X)
            K2 = self.k3a.K(X)
            K1 = self.k3.session.run(K1, feed_dict={X: X_data})
            K2 = self.k3a.session.run(K2, feed_dict={X: X_data})
            self.assertTrue(np.allclose(K1, K2))


class TestKernNaming(GPflowTestCase):
    def test_no_nesting_1(self):
        with self.test_context():
            k1 = gpflow.kernels.RBF(1)
            k2 = gpflow.kernels.Linear(2)
            k3 = k1 + k2
            k4 = gpflow.kernels.Matern32(1)
            k5 = k3 + k4
            self.assertTrue(k5.rbf is k1)
            self.assertTrue(k5.linear is k2)
            self.assertTrue(k5.matern32 is k4)

    def test_no_nesting_2(self):
        with self.test_context():
            k1 = gpflow.kernels.RBF(1) + gpflow.kernels.Linear(2)
            k2 = gpflow.kernels.Matern32(1) + gpflow.kernels.Matern52(2)
            k = k1 + k2
            self.assertTrue(hasattr(k, 'rbf'))
            self.assertTrue(hasattr(k, 'linear'))
            self.assertTrue(hasattr(k, 'matern32'))
            self.assertTrue(hasattr(k, 'matern52'))

    def test_simple(self):
        with self.test_context():
            k1 = gpflow.kernels.RBF(1)
            k2 = gpflow.kernels.Linear(2)
            k = k1 + k2
            self.assertTrue(k.rbf is k1)
            self.assertTrue(k.linear is k2)

    def test_duplicates_1(self):
        with self.test_context():
            k1 = gpflow.kernels.Matern32(1)
            k2 = gpflow.kernels.Matern32(43)
            k = k1 + k2
            self.assertTrue(k.matern32_1 is k1)
            self.assertTrue(k.matern32_2 is k2)

    def test_duplicates_2(self):
        with self.test_context():
            k1 = gpflow.kernels.Matern32(1)
            k2 = gpflow.kernels.Matern32(2)
            k3 = gpflow.kernels.Matern32(3)
            k = k1 + k2 + k3
            self.assertTrue(k.matern32_1 is k1)
            self.assertTrue(k.matern32_2 is k2)
            self.assertTrue(k.matern32_3 is k3)


class TestKernNamingProduct(GPflowTestCase):
    def test_no_nesting_1(self):
        with self.test_context():
            k1 = gpflow.kernels.RBF(1)
            k2 = gpflow.kernels.Linear(2)
            k3 = k1 * k2
            k4 = gpflow.kernels.Matern32(1)
            k5 = k3 * k4
            self.assertTrue(k5.rbf is k1)
            self.assertTrue(k5.linear is k2)
            self.assertTrue(k5.matern32 is k4)

    def test_no_nesting_2(self):
        with self.test_context():
            k1 = gpflow.kernels.RBF(1) * gpflow.kernels.Linear(2)
            k2 = gpflow.kernels.Matern32(1) * gpflow.kernels.Matern52(2)
            k = k1 * k2
            self.assertTrue(hasattr(k, 'rbf'))
            self.assertTrue(hasattr(k, 'linear'))
            self.assertTrue(hasattr(k, 'matern32'))
            self.assertTrue(hasattr(k, 'matern52'))

    def test_simple(self):
        with self.test_context():
            k1 = gpflow.kernels.RBF(1)
            k2 = gpflow.kernels.Linear(2)
            k = k1 * k2
            self.assertTrue(k.rbf is k1)
            self.assertTrue(k.linear is k2)

    def test_duplicates_1(self):
        with self.test_context():
            k1 = gpflow.kernels.Matern32(1)
            k2 = gpflow.kernels.Matern32(43)
            k = k1 * k2
            self.assertTrue(k.matern32_1 is k1)
            self.assertTrue(k.matern32_2 is k2)

    def test_duplicates_2(self):
        with self.test_context():
            k1 = gpflow.kernels.Matern32(1)
            k2 = gpflow.kernels.Matern32(2)
            k3 = gpflow.kernels.Matern32(3)
            k = k1 * k2 * k3
            self.assertTrue(k.matern32_1 is k1)
            self.assertTrue(k.matern32_2 is k2)
            self.assertTrue(k.matern32_3 is k3)


class TestARDInit(GPflowTestCase):
    """
    For ARD kernels, make sure that kernels can be instantiated with a single
    lengthscale or a suitable array of lengthscales
    """

    def test_scalar(self):
        with self.test_context():
            k1 = gpflow.kernels.RBF(3, lengthscales=2.3)
            k2 = gpflow.kernels.RBF(3, lengthscales=np.ones(3) * 2.3)
            k1_lengthscales = k1.lengthscales.read_value()
            k2_lengthscales = k2.lengthscales.read_value()
            self.assertTrue(np.all(k1_lengthscales == k2_lengthscales))

    def test_MLP(self):
        with self.test_context():
            k1 = gpflow.kernels.ArcCosine(3, weight_variances=1.23, ARD=True)
            k2 = gpflow.kernels.ArcCosine(3, weight_variances=np.ones(3) * 1.23, ARD=True)
            k1_variances = k1.weight_variances.read_value()
            k2_variances = k2.weight_variances.read_value()
            self.assertTrue(np.all(k1_variances == k2_variances))


class TestFeatureMap(GPflowTestCase):

    def setUp(self):
        self.kernels_with_approx = [gpflow.kernels.RBF, gpflow.kernels.Exponential,
                                    gpflow.kernels.Matern12, gpflow.kernels.Matern52,
                                    gpflow.kernels.Matern32]
        self.exact_kernels = [gpflow.kernels.Linear, gpflow.kernels.Constant, gpflow.kernels.Bias]
        ka = gpflow.kernels.Cosine(10)
        kb = gpflow.kernels.RBF(10)
        k_list = [ka, kb]
        self.non_implemented_kerns = [gpflow.kernels.Cosine(10), gpflow.kernels.ArcCosine(10),
                                      gpflow.kernels.Polynomial(1), gpflow.kernels.Add(k_list),
                                      gpflow.kernels.Prod(k_list),
                                      gpflow.kernels.PeriodicKernel(1)]
        # nb for some of these kernels we could define a feature transform but these have not been
        # implemented yet. For instance the Periodic is just RBF after cos/sin transform and
        # polynomial has a closed form solution.

    def _inner_k_evals(self, kern, x):
        feature_map = kern.feature_map
        kern.compile()

        with kern.graph.as_default():
            x_ph = tf.placeholder(tf.float64, x.shape)

        mapped_x = feature_map(x)
        k_via_lin = mapped_x @ mapped_x.T

        with decors.params_as_tensors_for(kern):
            k_via_k = kern.K(x_ph)

        fd = {x_ph: x}
        if kern.feeds:
            fd.update(kern.feeds)
        k_via_lin_evald = k_via_lin
        k_via_k_evald = kern.session.run(k_via_k, feed_dict=fd)
        return k_via_k_evald, k_via_lin_evald


    def test_feature_dot_product_matches_kernel_exactly(self):
        kernels_to_test = self.exact_kernels

        num_items = 1000
        rng = np.random.RandomState(100)

        x = rng.randn(num_items, 1)
        for kernel_class in kernels_to_test:
            kern = kernel_class(1, variance=4.41564)
            k_via_k_evald, k_via_lin_evald = self._inner_k_evals(kern, x)
            np.testing.assert_almost_equal(k_via_k_evald, k_via_lin_evald,
                                           err_msg="Failed on kernel: {}".format(str(type(kern))))

    def test_feature_dot_product_matches_kernel_exactly_multi_dimension(self):
        kernels_to_test = self.exact_kernels

        num_items = 1000
        num_orig_dims = 4
        slice_to_use = slice(1,3)
        rng = np.random.RandomState(100)

        x = rng.randn(num_items, num_orig_dims)
        for kernel_class in kernels_to_test:
            kern = kernel_class(2, variance=7.456, active_dims=slice_to_use)
            k_via_k_evald, k_via_lin_evald = self._inner_k_evals(kern, x)
            np.testing.assert_almost_equal(k_via_k_evald, k_via_lin_evald,
                                           err_msg="Failed on kernel: {}".format(str(type(kern))))


    def test_feature_dot_product_matches_kernel_roughly(self):
        # this one checks the approximate random features.
        # as these are not guaranteed to be exact they do not have to match exactly
        # so this is a really rough test and probably can only catch very large regressions
        kernels_to_test = self.kernels_with_approx

        num_items = 10
        rng = np.random.RandomState(100)

        x = rng.uniform(0, 10, (num_items, 1))
        for kernel_class in kernels_to_test:
            kern = kernel_class(1, variance=1.2, num_features_to_approx=10000, lengthscales=5.4)
            k_via_k_evald, k_via_lin_evald = self._inner_k_evals(kern, x)

            abs_diff = np.abs((k_via_k_evald - k_via_lin_evald))
            print("Max abs diff for kernel {} is {}. Max abs kernel value is {}.".format(str(type(kern)),
                                            np.max(abs_diff), np.max(np.abs(k_via_k_evald))))
            np.testing.assert_array_less(abs_diff, 0.15 * np.max(k_via_k_evald) * np.ones_like(k_via_lin_evald),
                                           err_msg="Failed on kernel: {}. Max absolute diff was {}".format(
                                               str(type(kern)), str(np.max(abs_diff))))

    def test_random_features_are_correct_dims(self):
        # Checks random features are correct shape.
        kernels_to_test = self.kernels_with_approx

        num_items = 10
        rng = np.random.RandomState(100)

        x = rng.uniform(0, 10, (num_items, 1))
        for kernel_class in kernels_to_test:
            kern = kernel_class(1, variance=1.2, num_features_to_approx=10000, lengthscales=5.4)
            kern.compile()
            mapped_x = kern.feature_map(x)
            self.assertEqual(mapped_x.shape, (num_items, 10000))

    def test_feature_dot_product_matches_kernel_roughly_multi_dim(self):
        # this one checks the approximate random features.
        # as these are not guaranteed to be exact they do not have to match exactly
        # so this is a really rough test and probably can only catch very large regressions
        kernels_to_test = self.kernels_with_approx

        num_items = 10
        num_orig_dims = 4
        slice_to_use = slice(1, 3)
        rng = np.random.RandomState(100)

        x = rng.uniform(0, 10, (num_items, num_orig_dims))
        for kernel_class in kernels_to_test:
            kern = kernel_class(2, variance=1.2, num_features_to_approx=10000, lengthscales=5.4, active_dims=slice_to_use)
            k_via_k_evald, k_via_lin_evald = self._inner_k_evals(kern, x)
            abs_diff = np.abs((k_via_k_evald - k_via_lin_evald))

            DEBUG_STR = False
            if DEBUG_STR:
                print("Max abs diff for kernel {} is {}. Max abs kernel value is {}.".format(
                    str(type(kern)), np.max(abs_diff), np.max(np.abs(k_via_k_evald))))
            np.testing.assert_array_less(abs_diff,
                                         0.15 * np.max(k_via_k_evald) * np.ones_like(k_via_lin_evald),
                                         err_msg="Failed on kernel: {}. Max absolute diff was {}".format(
                                               str(type(kern)), str(np.max(abs_diff))))

    def test_non_implemented_kernels_give_correct_error(self):
        kernels_with_no_linear_features = self.non_implemented_kerns
        for kernel_class in kernels_with_no_linear_features:
            kernel_class.compile()
            with self.assertRaises(NotImplementedError):
                res = kernel_class.feature_map(np.ones((10, 3), dtype=np.float64))
                print(res)


if __name__ == "__main__":
    unittest.main()
